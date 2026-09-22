"""Life Dashboard Companion webhook integration for Home Assistant."""

from __future__ import annotations

from hashlib import sha256
import hmac
import json
import logging
from typing import Any

from aiohttp import web

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_DEVICE_NAME,
    CONF_HMAC_SECRET,
    CONF_WEBHOOK_ID,
    DEVICE_HEALTH,
    DEVICE_SCREEN_TIME,
    DOMAIN,
    MANUFACTURER,
    PLATFORMS,
    SOURCE_HEALTH_CONNECT,
    SOURCE_HEALTHKIT_IOS,
    SOURCE_SCREEN_TIME,
)
from .runtime import LifeDashboardRuntime

_LOGGER = logging.getLogger(__name__)
_LEGACY_HISTORY_OPTION = "store_detailed_history"


def _device_identifier(entry_id: str, group: str) -> tuple[str, str]:
    return (DOMAIN, f"{entry_id}:{group}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Life Dashboard Webhook from a config entry."""
    runtime = LifeDashboardRuntime(hass, entry.entry_id)
    await runtime.async_load()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if _LEGACY_HISTORY_OPTION in entry.options:
        options = dict(entry.options)
        options.pop(_LEGACY_HISTORY_OPTION)
        hass.config_entries.async_update_entry(entry, options=options)

    webhook.async_register(
        hass,
        DOMAIN,
        f"Life Dashboard: {entry.data[CONF_DEVICE_NAME]}",
        entry.data[CONF_WEBHOOK_ID],
        _build_webhook_handler(entry),
        local_only=False,
        allowed_methods={"POST"},
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Life Dashboard Webhook config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove stored normalized data when the integration entry is deleted."""
    runtime = LifeDashboardRuntime(hass, entry.entry_id)
    await runtime.async_remove_store()


def _build_webhook_handler(entry: ConfigEntry):
    """Create an entry-bound webhook handler."""

    async def _async_handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        raw_body = await request.read()
        secret = entry.data.get(CONF_HMAC_SECRET) or entry.options.get(CONF_HMAC_SECRET)
        if secret:
            signature = request.headers.get("X-Signature", "")
            expected = "sha256=" + hmac.new(
                str(secret).encode("utf-8"), raw_body, sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                _LOGGER.warning(
                    "Rejected Life Dashboard webhook for %s because HMAC verification failed",
                    entry.data[CONF_DEVICE_NAME],
                )
                return web.Response(status=401, text="Invalid signature")

        try:
            payload: dict[str, Any] = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return web.Response(status=400, text="Invalid JSON")

        if not isinstance(payload, dict):
            return web.Response(status=400, text="Expected a JSON object")

        source = payload.get("source")
        if source not in {SOURCE_HEALTH_CONNECT, SOURCE_HEALTHKIT_IOS, SOURCE_SCREEN_TIME}:
            # Test pings or future payloads should still get a successful response so the
            # Android app can verify connectivity without creating bogus entities.
            return web.Response(status=204)

        runtime: LifeDashboardRuntime = hass.data[DOMAIN][entry.entry_id]
        try:
            await runtime.async_process_payload(payload)
            _update_device_registry(hass, entry, payload)
        except Exception:  # Return 5xx so Life Dashboard will retry transient failures.
            _LOGGER.exception(
                "Failed to process Life Dashboard webhook for %s",
                entry.data[CONF_DEVICE_NAME],
            )
            return web.Response(status=500, text="Webhook processing failed")
        return web.Response(status=204)

    return _async_handle_webhook


def _update_device_registry(
    hass: HomeAssistant, entry: ConfigEntry, payload: dict[str, Any]
) -> None:
    """Refresh device registry metadata from incoming payloads."""
    registry = dr.async_get(hass)
    phone_name = entry.data[CONF_DEVICE_NAME]
    source = payload.get("source")
    app_version = payload.get("app_version")

    if source in {SOURCE_HEALTH_CONNECT, SOURCE_HEALTHKIT_IOS}:
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={_device_identifier(entry.entry_id, DEVICE_HEALTH)},
            name=f"{phone_name} Health",
            manufacturer=MANUFACTURER,
            model="Health Connect" if source == SOURCE_HEALTH_CONNECT else "HealthKit",
            sw_version=app_version,
        )
    elif source == SOURCE_SCREEN_TIME:
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={_device_identifier(entry.entry_id, DEVICE_SCREEN_TIME)},
            name=f"{phone_name} Screen Time",
            manufacturer=MANUFACTURER,
            model=payload.get("device") or "Android Screen Time",
            sw_version=app_version,
        )
