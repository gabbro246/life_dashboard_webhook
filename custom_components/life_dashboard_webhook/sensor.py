"""Sensor platform for Life Dashboard Webhook."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DEVICE_NAME,
    DEVICE_HEALTH,
    DEVICE_SCREEN_TIME,
    DOMAIN,
    MANUFACTURER,
)
from .runtime import LifeDashboardRuntime
from .sensor_definitions import SensorDefinition, STATIC_SENSOR_DEFINITIONS


APP_ICON_FALLBACK = "mdi:application-outline"
CUSTOM_BRAND_ICON_FILES = (
    "www/community/custom-brand-icons/custom-brand-icons.js",
    "www/custom-brand-icons.js",
)
CUSTOM_BRAND_ICON_PATTERN = re.compile(r'^\s*"([^"]+)":\[', re.MULTILINE)

# Android package names whose user-facing names do not always match their PHU icon.
APP_ICON_ALIASES: dict[str, tuple[str, ...]] = {
    "com.amazon.mshop.android.shopping": ("amazon",),
    "com.android.chrome": ("google-chrome", "chrome"),
    "com.discord": ("discord",),
    "com.duolingo": ("duolingo",),
    "com.ebay.mobile": ("ebay",),
    "com.facebook.katana": ("facebook",),
    "com.facebook.orca": ("facebook-messenger", "messenger"),
    "com.google.android.apps.docs": ("google-drive",),
    "com.google.android.apps.maps": ("google-maps",),
    "com.google.android.apps.messaging": ("google-messages",),
    "com.google.android.apps.photos": ("google-photos",),
    "com.google.android.apps.youtube.music": ("youtube-music",),
    "com.google.android.calendar": ("google-calendar",),
    "com.google.android.gm": ("gmail",),
    "com.google.android.keep": ("google-keep",),
    "com.google.android.youtube": ("youtube",),
    "com.instagram.android": ("instagram",),
    "com.linkedin.android": ("linkedin",),
    "com.microsoft.office.outlook": ("microsoft-outlook", "outlook"),
    "com.microsoft.teams": ("microsoft-teams", "teams"),
    "com.netflix.mediaclient": ("netflix",),
    "com.paypal.android.p2pmobile": ("paypal",),
    "com.pinterest": ("pinterest",),
    "com.reddit.frontpage": ("reddit",),
    "com.snapchat.android": ("snapchat",),
    "com.spotify.music": ("spotify",),
    "com.twitter.android": ("x", "twitter"),
    "com.ubercab": ("uber",),
    "com.whatsapp": ("whatsapp",),
    "com.zhiliaoapp.musically": ("tiktok",),
    "org.telegram.messenger": ("telegram",),
    "tv.twitch.android.app": ("twitch",),
}


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


def _icon_name(value: str) -> str:
    """Convert an app label into the naming style used by PHU icons."""
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _app_icon(package: str, app_name: str, brand_icons: frozenset[str]) -> str:
    """Choose an installed brand icon for an app, with a safe MDI fallback."""
    app_slug = _icon_name(app_name)
    candidates = (
        *APP_ICON_ALIASES.get(package.casefold(), ()),
        app_slug,
        app_slug.replace("-", ""),
    )
    for candidate in candidates:
        if candidate and candidate in brand_icons:
            return f"phu:{candidate}"
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
    brand_icons = await hass.async_add_executor_job(
        _load_custom_brand_icons, hass.config.path
    )

    entities: list[SensorEntity] = [
        LifeDashboardSensor(entry, runtime, definition)
        for definition in STATIC_SENSOR_DEFINITIONS
    ]

    added_apps: set[str] = set()
    for package in sorted(runtime.known_apps):
        entities.append(
            LifeDashboardAppSensor(entry, runtime, package, brand_icons)
        )
        added_apps.add(package)

    async_add_entities(entities)

    @callback
    def _add_app(package: str, _name: str) -> None:
        if package in added_apps:
            return
        added_apps.add(package)
        async_add_entities(
            [LifeDashboardAppSensor(entry, runtime, package, brand_icons)]
        )

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
        self._attr_unique_id = f"{entry.entry_id}:{definition.key}"
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
            name = f"{phone_name} Screen Time"
            model = "Android Screen Time"
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
    ) -> None:
        self._entry = entry
        self._runtime = runtime
        self._package = package
        self._attr_unique_id = f"{entry.entry_id}:screen_app:{package}"
        self._attr_icon = _app_icon(
            package,
            runtime.known_apps.get(package, runtime.get_app_display_name(package)),
            brand_icons,
        )

    @property
    def name(self) -> str:
        """Return a name that stays unique as more apps are discovered."""
        app_name = self._runtime.get_app_display_name(self._package)
        return f"{app_name} screen time today"

    @property
    def device_info(self) -> DeviceInfo:
        """Attach app sensors to the Screen Time device."""
        phone_name = self._entry.data[CONF_DEVICE_NAME]
        return DeviceInfo(
            identifiers={_device_identifier(self._entry.entry_id, DEVICE_SCREEN_TIME)},
            name=f"{phone_name} Screen Time",
            manufacturer=MANUFACTURER,
            model="Android Screen Time",
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
