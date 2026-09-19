# Life Dashboard Webhook

<p align="center">
  <img src="custom_components/life_dashboard_webhook/brand/icon.png" alt="Life Dashboard Webhook icon" width="160">
</p>

Life Dashboard Webhook brings health and screen-time data from
[Life Dashboard Companion](https://github.com/owen282000/life-dashboard-companion-app)
into Home Assistant.

## What it does

The integration creates separate Health and Screen Time devices for each
phone. Their sensors include daily activity, body measurements, sleep,
exercise, nutrition, phone usage, and individual app usage when that data is
available.

Sensors without data are disabled by default, so the device pages stay tidy.
You can enable any additional sensor from its entity settings.

## Install with HACS

[![Open Life Dashboard Webhook in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=gabbro246&repository=life_dashboard_webhook&category=integration)

1. Select the button above from a device where you are signed in to Home
   Assistant, then confirm the repository in HACS.
2. In HACS, download **Life Dashboard Webhook**.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services**, choose **Add integration**, and
   search for **Life Dashboard Webhook**.

You need [HACS](https://hacs.xyz/) installed first. If the button cannot open
your Home Assistant, add
`https://github.com/gabbro246/life_dashboard_webhook` in HACS as an
**Integration** repository instead.

## Connect a phone

When adding the integration, give the phone a clear name. Home Assistant then
shows a dedicated webhook URL. Use that same URL for the Health Connect and
Screen Time webhooks in Life Dashboard Companion.

You can optionally add a signing secret to verify that incoming data came from
your phone. Enter the same secret in Home Assistant and Life Dashboard
Companion.

Add the integration again for each additional phone. To change a phone name or
signing secret later, open **Settings → Devices & services → Life Dashboard
Webhook**, select the phone, and choose **Configure**.

## Manual installation

Copy `custom_components/life_dashboard_webhook` into the `custom_components`
directory in your Home Assistant configuration, then restart Home Assistant.

## License

[MIT](LICENSE)
