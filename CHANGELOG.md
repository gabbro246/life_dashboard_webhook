# Changelog

## 0.3.1

- Added a choice of Health, ScreenTime, or both for each phone, which can be changed later.
- Simplified entity names, such as `phone_screentime_today` and `phone_health_steps_today`.
- Made the default entity selection more consistent and reduced unused clutter.
- Improved app icons and made app-version names clearer.

## 0.2.7

- Activity sensors now work directly in Statistics graph cards with hourly or daily periods.
- Stopped creating separate detailed-history statistics and removed the setting.

## 0.2.6

- Fixed detailed history for phones with newer Home Assistant identifiers.

## 0.2.5

- Fixed detailed history not appearing for some phones.

## 0.2.4

- Added optional detailed history for accurate health and screen-time graphs, even after a delayed phone sync.
- Added clearer screen-time and app icons, with supported brand icons used when available.

## 0.2.3
- Individual app sensors now start disabled, while the main screen-time summaries stay enabled.
- App names are clearer, duplicate names are distinguished, and package names are included.

## 0.2.2
- Added clear version numbers and release notes to HACS updates.
- Updated the integration icon with a transparent, consistent design.
- Made the setup instructions shorter and easier to follow.

## 0.2.1
- The integration can now be installed and updated through HACS.

## 0.2.0
- Sensors without available data are now disabled by default.
- App screen-time sensors now appear after an app exceeds 10 minutes of use in a day.
