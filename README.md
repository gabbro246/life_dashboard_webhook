# Life Dashboard Webhook

<p align="center">
  <img src="custom_components/life_dashboard_webhook/brand/icon.png" alt="Life Dashboard Webhook icon" width="160">
</p>

Life Dashboard Webhook brings health and ScreenTime data from
[Life Dashboard Companion](https://github.com/owen282000/life-dashboard-companion-app)
into Home Assistant.

## What it does

The integration creates separate Health and ScreenTime devices for each
phone. Their sensors include daily activity, body measurements, sleep,
exercise, nutrition, phone usage, and individual app usage when that data is
available.

Sensors are enabled by default only when their data has been received.
Latest-interval sensors, yesterday and seven-day ScreenTime summaries, and
individual app sensors are opt-in so the device pages stay focused. Enable any
of them from their entity settings when you need them.

[Custom Brand Icons](https://github.com/elax46/custom-brand-icons) is
recommended for recognizable icons on individual app ScreenTime sensors. When
it is not installed or an app has no matching icon, a standard app icon is used.

## Statistics graphs

Add the existing **Steps today**, **Distance today**, calorie, **Screen time
today**, or app screen-time entity directly to a Statistics graph card. Choose
**Change** as the statistic, then switch the card period between **Hour** and
**Day**. No additional sensor or statistic ID is needed.

For values such as heart rate, weight, or temperature, use **Mean**, **Minimum**,
or **Maximum** instead.

Hourly bars reflect when the phone sends updates to Home Assistant. More
frequent phone syncs give more accurate hourly distribution.

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

When adding the integration, choose Health, ScreenTime, or both. Use the
provided webhook URL for the selected features in Life Dashboard Companion.

You can optionally add a signing secret to verify that incoming data came from
your phone. Enter the same secret in Home Assistant and Life Dashboard
Companion.

Add the integration again for each additional phone. To change its settings,
select the phone under **Settings → Devices & services → Life Dashboard Webhook**
and choose **Configure**.

## Manual installation

Copy `custom_components/life_dashboard_webhook` into the `custom_components`
directory in your Home Assistant configuration, then restart Home Assistant.

## License

[MIT](LICENSE)
