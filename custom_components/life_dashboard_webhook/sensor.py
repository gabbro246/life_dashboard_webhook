"""Sensor platform for Life Dashboard Webhook."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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


def _device_identifier(entry_id: str, group: str) -> tuple[str, str]:
    return (DOMAIN, f"{entry_id}:{group}")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up static sensors and dynamically discovered app sensors."""
    runtime: LifeDashboardRuntime = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        LifeDashboardSensor(entry, runtime, definition)
        for definition in STATIC_SENSOR_DEFINITIONS
    ]

    added_apps: set[str] = set()
    for package in sorted(runtime.known_apps):
        entities.append(LifeDashboardAppSensor(entry, runtime, package))
        added_apps.add(package)

    async_add_entities(entities)

    @callback
    def _add_app(package: str, _name: str) -> None:
        if package in added_apps:
            return
        added_apps.add(package)
        async_add_entities([LifeDashboardAppSensor(entry, runtime, package)])

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
    _attr_icon = "mdi:application"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        entry: ConfigEntry,
        runtime: LifeDashboardRuntime,
        package: str,
    ) -> None:
        self._entry = entry
        self._runtime = runtime
        self._package = package
        self._attr_unique_id = f"{entry.entry_id}:screen_app:{package}"

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
