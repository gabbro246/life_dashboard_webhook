# Life Dashboard Webhook

A Home Assistant custom integration that receives health and screen-time data from Life Dashboard Companion and exposes it as sensor entities.

## Install with HACS

1. Open HACS in Home Assistant.
2. Open the three-dot menu and select **Custom repositories**.
3. Add `https://github.com/gabbro246/life_dashboard_webhook` and choose **Integration** as the category.
4. Open **Life Dashboard Webhook** in HACS and select **Download**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration**, search for **Life Dashboard Webhook**, and follow the setup steps.

The setup flow creates a dedicated webhook URL for one phone. Use that URL for both the Health Connect and Screen Time webhooks in Life Dashboard Companion. Add the integration again for each additional phone.

If you configure an optional HMAC signing secret, use the same secret in Life Dashboard Companion.

## Updates

HACS will show new versions on its dashboard. Select **Update** there, then restart Home Assistant when prompted.

## Manual installation

Copy `custom_components/life_dashboard_webhook` into the `custom_components` directory inside your Home Assistant configuration directory, then restart Home Assistant.
