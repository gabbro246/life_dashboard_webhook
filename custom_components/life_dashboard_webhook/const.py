"""Constants for the Life Dashboard Webhook integration."""

from homeassistant.const import Platform

DOMAIN = "life_dashboard_webhook"
PLATFORMS = [Platform.SENSOR]

CONF_DEVICE_NAME = "device_name"
CONF_HMAC_SECRET = "hmac_secret"
CONF_WEBHOOK_ID = "webhook_id"

SOURCE_HEALTH_CONNECT = "health_connect"
SOURCE_HEALTHKIT_IOS = "healthkit_ios"
SOURCE_SCREEN_TIME = "screen_time"

DEVICE_HEALTH = "health"
DEVICE_SCREEN_TIME = "screen_time"

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = "life_dashboard_webhook"

INTEGRATION_NAME = "Life Dashboard Webhook"
MANUFACTURER = "Life Dashboard Companion"
