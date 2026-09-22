"""Sensor platform for Life Dashboard Webhook."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DEVICE_NAME,
    CONF_HEALTH_ENABLED,
    CONF_SCREENTIME_ENABLED,
    DEVICE_HEALTH,
    DEVICE_SCREEN_TIME,
    DOMAIN,
    MANUFACTURER,
)
from .runtime import LifeDashboardRuntime
from .sensor_definitions import SensorDefinition, STATIC_SENSOR_DEFINITIONS


APP_ICON_FALLBACK = "mdi:application"
CUSTOM_BRAND_ICON_FILES = (
    "www/community/custom-brand-icons/custom-brand-icons.js",
    "www/custom-brand-icons.js",
)
CUSTOM_BRAND_ICON_PATTERN = re.compile(r'^\s*"([^"]+)":\[', re.MULTILINE)
MDI_ICON_FILE = Path(__file__).with_name("mdi_icon_names.json")

APP_NAME_SUFFIXES = frozenset({"android", "app", "beta", "mobile", "pro"})
PHU_NAME_SUFFIXES = frozenset({"icon", "logo"})
AMBIGUOUS_APP_WORDS = frozenset(
    {
        "app",
        "camera",
        "gallery",
        "home",
        "mail",
        "maps",
        "messages",
        "mobile",
        "music",
        "phone",
        "photos",
        "smart",
        "video",
    }
)


def _custom_brand_icons_loaded(hass: HomeAssistant) -> bool:
    """Return whether PHU is configured globally in the Home Assistant frontend."""
    manager = hass.data.get(DATA_EXTRA_MODULE_URL)
    urls = getattr(manager, "urls", ())
    return any(
        isinstance(url, str)
        and url.partition("?")[0].rstrip("/").endswith("/custom-brand-icons.js")
        for url in urls
    )


def _load_custom_brand_icons(config_path: Callable[[str], str]) -> frozenset[str]:
    """Return the PHU icons found in an installed Custom Brand Icons file."""
    for relative_path in CUSTOM_BRAND_ICON_FILES:
        icon_file = Path(config_path(relative_path))
        if not icon_file.is_file():
            continue
        try:
            contents = icon_file.read_text(encoding="utf-8")
        except OSError:
            continue
        return frozenset(CUSTOM_BRAND_ICON_PATTERN.findall(contents))
    return frozenset()


def _load_mdi_icons() -> frozenset[str]:
    """Return the bundled list of valid Material Design Icon names."""
    try:
        names = json.loads(MDI_ICON_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    if not isinstance(names, list):
        return frozenset()
    return frozenset(name for name in names if isinstance(name, str))


def _name_tokens(value: str) -> tuple[str, ...]:
    """Normalize an app or PHU name into comparable words."""
    ascii_name = (
        unicodedata.normalize("NFKD", value.casefold())
        .encode("ascii", "ignore")
        .decode()
    )
    return tuple(re.findall(r"[a-z0-9]+", ascii_name))


def _without_suffixes(
    tokens: tuple[str, ...], suffixes: frozenset[str]
) -> tuple[str, ...]:
    """Remove generic trailing words without discarding the whole name."""
    end = len(tokens)
    while end > 1 and tokens[end - 1] in suffixes:
        end -= 1
    return tokens[:end]


def _matching_icon(
    app_name: str,
    icon_names: frozenset[str],
    icon_suffixes: frozenset[str] = frozenset(),
    *,
    allow_app_prefix: bool = False,
    allow_app_suffix: bool = False,
    allow_icon_prefix: bool = False,
) -> str | None:
    """Find the most confident icon match using names only."""
    app_tokens = _name_tokens(app_name)
    if not app_tokens:
        return None
    app_core = _without_suffixes(app_tokens, APP_NAME_SUFFIXES)
    app_compact = "".join(app_tokens)
    app_core_compact = "".join(app_core)
    best: tuple[int, int, str] | None = None

    for icon in icon_names:
        icon_tokens = _name_tokens(icon)
        if not icon_tokens:
            continue
        icon_core = _without_suffixes(icon_tokens, icon_suffixes)
        icon_compact = "".join(icon_tokens)
        icon_core_compact = "".join(icon_core)

        if icon_tokens == app_tokens:
            score = 500
        elif icon_compact == app_compact:
            score = 490
        elif icon_core == app_core:
            score = 450
        elif icon_core_compact == app_core_compact:
            score = 440
        elif (
            allow_app_suffix
            and len(app_core) > len(icon_core)
            and app_core[-len(icon_core) :] == icon_core
            and len(icon_core_compact) >= 4
            and icon_core[0] not in AMBIGUOUS_APP_WORDS
        ):
            score = 400 + len(icon_core_compact)
        elif (
            allow_app_prefix
            and len(app_core) > len(icon_core)
            and app_core[: len(icon_core)] == icon_core
            and len(icon_core_compact) >= 5
            and icon_core[0] not in AMBIGUOUS_APP_WORDS
        ):
            score = 300 + len(icon_core_compact)
        elif (
            allow_icon_prefix
            and len(icon_core) > len(app_core)
            and icon_core[-len(app_core) :] == app_core
            and len(app_core_compact) >= 4
            and app_core[0] not in AMBIGUOUS_APP_WORDS
        ):
            score = 280 + len(app_core_compact)
        else:
            continue

        candidate = (score, -len(icon_tokens), icon)
        if best is None or candidate > best:
            best = candidate

    return best[2] if best else None


def _app_icon(
    app_name: str,
    brand_icons: frozenset[str],
    mdi_icons: frozenset[str],
) -> str:
    """Choose a matching PHU icon, matching MDI icon, or generic fallback."""
    if match := _matching_icon(
        app_name,
        brand_icons,
        PHU_NAME_SUFFIXES,
        allow_app_prefix=True,
    ):
        return f"phu:{match}"
    if match := _matching_icon(
        app_name,
        mdi_icons,
        allow_app_suffix=True,
        allow_icon_prefix=True,
    ):
        return f"mdi:{match}"
    return APP_ICON_FALLBACK


def _device_identifier(entry_id: str, group: str) -> tuple[str, str]:
    return (DOMAIN, f"{entry_id}:{group}")


def _source_reset_time(
    data: dict[str, Any] | None, keys: tuple[str, ...]
) -> datetime | None:
    """Parse a reset timestamp from normalized source attributes."""
    attrs = data.get("attributes") if data else None
    if not isinstance(attrs, dict):
        return None
    for key in keys:
        value = attrs.get(key)
        if not isinstance(value, str):
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        return parsed
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up static sensors and dynamically discovered app sensors."""
    runtime: LifeDashboardRuntime = hass.data[DOMAIN][entry.entry_id]
    health_enabled = bool(entry.data.get(CONF_HEALTH_ENABLED, True))
    screentime_enabled = bool(entry.data.get(CONF_SCREENTIME_ENABLED, True))
    brand_icons = (
        await hass.async_add_executor_job(
            _load_custom_brand_icons, hass.config.path
        )
        if _custom_brand_icons_loaded(hass)
        else frozenset()
    )
    mdi_icons = await hass.async_add_executor_job(_load_mdi_icons)

    entities: list[SensorEntity] = [
        LifeDashboardSensor(entry, runtime, definition)
        for definition in STATIC_SENSOR_DEFINITIONS
        if (
            (definition.device_group == DEVICE_HEALTH and health_enabled)
            or (
                definition.device_group == DEVICE_SCREEN_TIME
                and screentime_enabled
            )
        )
    ]

    added_apps: set[str] = set()
    if screentime_enabled:
        for package in sorted(runtime.known_apps):
            entities.append(
                LifeDashboardAppSensor(
                    entry, runtime, package, brand_icons, mdi_icons
                )
            )
            added_apps.add(package)

    async_add_entities(entities)

    @callback
    def _add_app(package: str, _name: str) -> None:
        if package in added_apps:
            return
        added_apps.add(package)
        async_add_entities(
            [
                LifeDashboardAppSensor(
                    entry, runtime, package, brand_icons, mdi_icons
                )
            ]
        )

    if screentime_enabled:
        entry.async_on_unload(runtime.add_app_listener(_add_app))


class LifeDashboardSensor(SensorEntity):
    """A scalar sensor normalized from Life Dashboard webhook data."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        runtime: LifeDashboardRuntime,
        definition: SensorDefinition,
    ) -> None:
        self._entry = entry
        self._runtime = runtime
        self._definition = definition
        group = (
            "health"
            if definition.device_group == DEVICE_HEALTH
            else "screentime"
        )
        self._attr_unique_id = f"{entry.entry_id}:{group}:{definition.key}"
        self._attr_name = definition.name
        self._attr_native_unit_of_measurement = definition.unit
        self._attr_icon = definition.icon
        self._attr_state_class = definition.state_class
        self._attr_device_class = (
            SensorDeviceClass.TIMESTAMP if definition.timestamp else None
        )
        self._attr_entity_category = definition.entity_category
        self._attr_suggested_display_precision = definition.suggested_display_precision
        data = runtime.get_state(definition.key)
        self._attr_entity_registry_enabled_default = (
            definition.enabled_default
            if definition.enabled_default is not None
            else bool(data is not None and data.get("value") is not None)
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the requested Health or Screen Time device."""
        phone_name = self._entry.data[CONF_DEVICE_NAME]
        if self._definition.device_group == DEVICE_HEALTH:
            name = f"{phone_name} Health"
            model = "Health Connect"
        else:
            name = f"{phone_name} ScreenTime"
            model = "Android ScreenTime"
        return DeviceInfo(
            identifiers={_device_identifier(self._entry.entry_id, self._definition.device_group)},
            name=name,
            manufacturer=MANUFACTURER,
            model=model,
        )

    @property
    def native_value(self) -> Any:
        """Return the current normalized value."""
        data = self._runtime.get_state(self._definition.key)
        if not data:
            return None
        value = data.get("value")
        if self._definition.timestamp and isinstance(value, str):
            parsed: datetime | None = dt_util.parse_datetime(value)
            return parsed
        return value

    @property
    def last_reset(self) -> datetime | None:
        """Return the source-defined reset time for accumulated counters."""
        return _source_reset_time(
            self._runtime.get_state(self._definition.key),
            self._definition.reset_keys,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return compact source metadata."""
        data = self._runtime.get_state(self._definition.key)
        if not data:
            return None
        attrs = data.get("attributes")
        return attrs if isinstance(attrs, dict) else None

    async def async_added_to_hass(self) -> None:
        """Subscribe to push updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_state_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class LifeDashboardAppSensor(SensorEntity):
    """Today's screen time for one Android application package."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        entry: ConfigEntry,
        runtime: LifeDashboardRuntime,
        package: str,
        brand_icons: frozenset[str] = frozenset(),
        mdi_icons: frozenset[str] = frozenset(),
    ) -> None:
        self._entry = entry
        self._runtime = runtime
        self._package = package
        self._attr_unique_id = f"{entry.entry_id}:screentime:app:{package}"
        self._attr_icon = _app_icon(
            runtime.known_apps.get(package, runtime.get_app_display_name(package)),
            brand_icons,
            mdi_icons,
        )

    @property
    def name(self) -> str:
        """Return a name that stays unique as more apps are discovered."""
        app_name = self._runtime.get_app_display_name(self._package)
        return f"{app_name} today"

    @property
    def device_info(self) -> DeviceInfo:
        """Attach app sensors to the Screen Time device."""
        phone_name = self._entry.data[CONF_DEVICE_NAME]
        return DeviceInfo(
            identifiers={_device_identifier(self._entry.entry_id, DEVICE_SCREEN_TIME)},
            name=f"{phone_name} ScreenTime",
            manufacturer=MANUFACTURER,
            model="Android ScreenTime",
        )

    @property
    def native_value(self) -> Any:
        data = self._runtime.get_state(f"screen_app::{self._package}")
        return data.get("value") if data else None

    @property
    def last_reset(self) -> datetime | None:
        """Return midnight on the source day as the app counter reset."""
        return _source_reset_time(
            self._runtime.get_state(f"screen_app::{self._package}"), ("date",)
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self._runtime.get_state(f"screen_app::{self._package}")
        if not data:
            return {"package": self._package}
        attrs = data.get("attributes")
        return {**attrs, "package": self._package} if isinstance(attrs, dict) else {
            "package": self._package
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_state_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
