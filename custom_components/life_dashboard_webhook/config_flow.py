"""Config flow for Life Dashboard Webhook."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_NAME,
    CONF_HMAC_SECRET,
    CONF_STORE_DETAILED_HISTORY,
    CONF_WEBHOOK_ID,
    DOMAIN,
)


def _webhook_url(hass, webhook_id: str) -> str:
    """Generate a usable URL, falling back to a placeholder if HA has no base URL."""
    try:
        return webhook.async_generate_url(hass, webhook_id)
    except Exception:  # Home Assistant can raise when no internal/external URL is configured.
        return f"https://YOUR_HOME_ASSISTANT_URL{webhook.async_generate_path(webhook_id)}"


class LifeDashboardWebhookConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for one Android device."""

    VERSION = 1

    def __init__(self) -> None:
        self._pending: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a dedicated webhook for one phone."""
        if user_input is not None:
            webhook_id = webhook.async_generate_id()
            device_name = str(user_input[CONF_DEVICE_NAME]).strip()
            secret = str(user_input.get(CONF_HMAC_SECRET, "")).strip()
            self._pending = {
                CONF_DEVICE_NAME: device_name,
                CONF_WEBHOOK_ID: webhook_id,
                CONF_HMAC_SECRET: secret,
            }
            await self.async_set_unique_id(webhook_id)
            return await self.async_step_confirm()

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_NAME, default="Android phone"): selector.TextSelector(),
                vol.Optional(CONF_HMAC_SECRET, default=""): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the URL before creating the entry."""
        if self._pending is None:
            return self.async_abort(reason="missing_setup_data")

        if user_input is not None:
            return self.async_create_entry(
                title=self._pending[CONF_DEVICE_NAME], data=self._pending
            )

        url = _webhook_url(self.hass, self._pending[CONF_WEBHOOK_ID])
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"webhook_url": url},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return options flow."""
        return LifeDashboardWebhookOptionsFlow(config_entry)


class LifeDashboardWebhookOptionsFlow(OptionsFlow):
    """Allow viewing the webhook URL and updating the device label/HMAC secret."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and edit entry options."""
        current_name = self._entry.data[CONF_DEVICE_NAME]
        current_secret = self._entry.data.get(CONF_HMAC_SECRET, "")
        current_history = self._entry.options.get(CONF_STORE_DETAILED_HISTORY, True)
        if user_input is not None:
            name = str(user_input[CONF_DEVICE_NAME]).strip()
            secret = str(user_input.get(CONF_HMAC_SECRET, "")).strip()
            new_data = dict(self._entry.data)
            new_data[CONF_DEVICE_NAME] = name
            new_data[CONF_HMAC_SECRET] = secret
            new_options = dict(self._entry.options)
            new_options[CONF_STORE_DETAILED_HISTORY] = bool(
                user_input.get(CONF_STORE_DETAILED_HISTORY, True)
            )
            self.hass.config_entries.async_update_entry(
                self._entry, data=new_data, options=new_options, title=name
            )
            self.hass.config_entries.async_schedule_reload(self._entry.entry_id)
            return self.async_create_entry(title="", data={})

        url = _webhook_url(self.hass, self._entry.data[CONF_WEBHOOK_ID])
        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_NAME, default=current_name): selector.TextSelector(),
                vol.Optional(CONF_HMAC_SECRET, default=current_secret): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional(
                    CONF_STORE_DETAILED_HISTORY, default=current_history
                ): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={"webhook_url": url},
        )
