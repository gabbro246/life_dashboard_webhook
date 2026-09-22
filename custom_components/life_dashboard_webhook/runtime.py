"""Runtime data container for Life Dashboard Webhook."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY_PREFIX, STORAGE_VERSION
from .history import async_import_history
from .parser import normalize_health, normalize_screen_time, resolve_app_names

_LOGGER = logging.getLogger(__name__)


def _sort_value(value: Any) -> tuple[int, float | str]:
    """Return a comparable freshness value for ISO timestamps or YYYY-MM-DD dates."""
    if not isinstance(value, str) or not value:
        return (0, "")
    try:
        return (2, datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return (1, value)


def _state_freshness(state: dict[str, Any]) -> tuple[int, float | str]:
    """Extract the best event/date marker from a normalized state."""
    attrs = state.get("attributes")
    if isinstance(attrs, dict):
        for key in (
            "date",
            "end_date",
            "session_end_time",
            "end_time",
            "bucket_end",
            "time",
            "start_time",
            "bucket_start",
        ):
            if key in attrs:
                value = _sort_value(attrs.get(key))
                if value[0]:
                    return value
    # Diagnostic last-sync entities carry the timestamp as their state value.
    return _sort_value(state.get("value"))


def _prefer_incoming(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> bool:
    """Prevent historical/backfill payloads from rolling a current entity backward."""
    if existing is None:
        return True

    existing_attrs = existing.get("attributes")
    incoming_attrs = incoming.get("attributes")
    if isinstance(existing_attrs, dict) and isinstance(incoming_attrs, dict):
        existing_bucket = existing_attrs.get("bucket_start")
        incoming_bucket = incoming_attrs.get("bucket_start")
        if existing_bucket and existing_bucket == incoming_bucket:
            # A completed bucket can later be resent with only late-arriving samples.
            # For a current-value entity, retaining the fuller bucket is safer than
            # replacing it with a smaller partial aggregate.
            existing_count = existing_attrs.get("sample_count")
            incoming_count = incoming_attrs.get("sample_count")
            if isinstance(existing_count, (int, float)) and isinstance(
                incoming_count, (int, float)
            ):
                if incoming_count < existing_count:
                    return False

    old_freshness = _state_freshness(existing)
    new_freshness = _state_freshness(incoming)
    if old_freshness[0] and new_freshness[0]:
        return new_freshness >= old_freshness
    return True

StateListener = Callable[[], None]
AppListener = Callable[[str, str], None]


class LifeDashboardRuntime:
    """Hold normalized states and screen-time app discovery for one phone."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.states: dict[str, dict[str, Any]] = {}
        self.known_apps: dict[str, str] = {}
        self._state_listeners: set[StateListener] = set()
        self._app_listeners: set[AppListener] = set()
        self._store = Store[dict[str, Any]](
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry_id}"
        )

    async def async_load(self) -> None:
        """Load persisted normalized state."""
        data = await self._store.async_load()
        if not isinstance(data, dict):
            return
        states = data.get("states")
        apps = data.get("known_apps")
        if isinstance(states, dict):
            self.states = {
                str(key): value
                for key, value in states.items()
                if isinstance(value, dict) and "value" in value
            }
        if isinstance(apps, dict):
            self.known_apps = {
                str(package): str(name)
                for package, name in apps.items()
                if isinstance(package, str) and isinstance(name, str)
            }

    async def async_save(self) -> None:
        """Persist compact normalized states, not raw webhook payloads."""
        await self._store.async_save(
            {"states": self.states, "known_apps": self.known_apps}
        )

    async def async_remove_store(self) -> None:
        """Delete persisted state when the config entry is removed."""
        await self._store.async_remove()

    def get_state(self, key: str) -> dict[str, Any] | None:
        """Return normalized data for one sensor."""
        return self.states.get(key)

    def get_app_display_name(self, package: str) -> str:
        """Return the current, unique display name for an app package."""
        return resolve_app_names(self.known_apps).get(package, package)

    @callback
    def add_state_listener(self, listener: StateListener) -> Callable[[], None]:
        """Subscribe to normalized state changes."""
        self._state_listeners.add(listener)

        @callback
        def _remove() -> None:
            self._state_listeners.discard(listener)

        return _remove

    @callback
    def add_app_listener(self, listener: AppListener) -> Callable[[], None]:
        """Subscribe to newly discovered screen-time apps."""
        self._app_listeners.add(listener)

        @callback
        def _remove() -> None:
            self._app_listeners.discard(listener)

        return _remove

    async def async_process_payload(
        self,
        payload: dict[str, Any],
        *,
        store_detailed_history: bool = True,
        device_name: str = "Life Dashboard",
    ) -> str:
        """Normalize one webhook payload and notify entities."""
        source = payload.get("source")
        newly_discovered: dict[str, str] = {}

        if source in {"health_connect", "healthkit_ios"}:
            updates = normalize_health(payload)
        elif source == "screen_time":
            updates, discovered = normalize_screen_time(payload)
            newly_discovered = {
                package: name
                for package, name in discovered.items()
                if package not in self.known_apps
            }
            self.known_apps.update(discovered)
        else:
            _LOGGER.debug("Ignoring unsupported Life Dashboard source: %s", source)
            return "ignored"

        if store_detailed_history:
            await async_import_history(self.hass, self.entry_id, payload, device_name)

        for key, incoming in updates.items():
            if _prefer_incoming(self.states.get(key), incoming):
                self.states[key] = incoming

        if source == "screen_time":
            display_names = resolve_app_names(self.known_apps)
            for package, name in display_names.items():
                state = self.states.get(f"screen_app::{package}")
                if not state:
                    continue
                attrs = state.get("attributes")
                if not isinstance(attrs, dict):
                    attrs = {}
                    state["attributes"] = attrs
                attrs["package"] = package
                attrs["app_name"] = name
            top_app = self.states.get("screen_top_app")
            if top_app and isinstance(top_app.get("attributes"), dict):
                top_package = top_app["attributes"].get("package")
                if isinstance(top_package, str) and top_package in display_names:
                    top_app["value"] = display_names[top_package]
        await self.async_save()

        for package, name in newly_discovered.items():
            for listener in tuple(self._app_listeners):
                listener(package, name)
        for listener in tuple(self._state_listeners):
            listener()

        return str(source)
