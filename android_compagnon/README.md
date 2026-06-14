# GPS Tracker

A simple personal GPS activity tracker for Android. Pick an activity (bike, hike,
ski touring), record a track that keeps running in the background, pause/stop, then
manage your saved recordings (view on an OpenStreetMap map, rename, delete, export
as GPX).

## Features

- Choose an activity: Bike, Hike, Ski touring.
- Live recording with distance, duration, current speed and elevation gain.
- Background-safe recording via an Android foreground service (persistent
  notification keeps tracking alive when the screen is off / app is backgrounded).
- Pause / resume / stop.
- Map display (OpenStreetMap tiles, no API key) of the live and saved tracks.
- Manage recordings: rename, delete.
- Export / share any recording as a standard `.gpx` file.
- All data stored locally in SQLite. No accounts, no cloud.

## Tech stack

- Flutter + Dart, state via `provider`.
- `geolocator` (GPS), `flutter_foreground_task` (background service),
  `flutter_map` + `latlong2` (OSM map), `sqflite` (storage),
  `gpx` + `share_plus` (export).

## Project layout

```
lib/
  main.dart                      App entry, providers, theme
  models/                        ActivityType, Track, TrackPoint
  data/                          SQLite database + GPX exporter
  services/                      Location stream + foreground service
  state/recording_controller.dart  Live session: GPS, stats, persistence
  ui/                            Home, activity picker, recording, detail
  utils/formatting.dart          Distance/time/speed formatting
android/                         Manifest (permissions + service) + Gradle
```

## Setup & run

This repo contains the application source and the customized Android config.
A few generated platform files (the Gradle wrapper binary, etc.) are not checked
in, so the first time you set up:

1. Install the [Flutter SDK](https://docs.flutter.dev/get-started/install) and
   Android Studio (Android SDK + a device/emulator).

2. From the project root, generate the missing platform scaffolding. This adds
   the Gradle wrapper without touching `lib/` or `pubspec.yaml`:

   ```bash
   flutter create --platforms=android .
   ```

   Note: `flutter create` may overwrite `android/app/src/main/AndroidManifest.xml`,
   `android/app/build.gradle` and `android/app/src/main/kotlin/.../MainActivity.kt`
   with defaults. If you ran it, restore the versions from this repo (they contain
   the location permissions and the foreground-service declaration that the app
   needs). Easiest: commit first, run `flutter create`, then `git checkout` those
   three files.

3. Fetch dependencies and run on a connected device:

   ```bash
   flutter pub get
   flutter run
   ```

## Permissions

On first recording the app requests:

- Location ("while using the app", then "allow all the time" for reliable
  background tracking).
- Notifications (Android 13+) for the persistent recording notification.

For best background reliability, grant "Allow all the time" location and disable
battery optimization for the app in Android settings.

## Notes

- OpenStreetMap tiles are used under the
  [OSM tile usage policy](https://operations.osmfoundation.org/policies/tiles/);
  this is fine for personal use.
- Plugin APIs evolve. If `flutter pub get` resolves a newer
  `flutter_foreground_task` whose `TaskHandler` signatures differ, adjust
  `lib/services/recording_service.dart` accordingly (the analyzer will point it out).
- iOS is not configured (Android-only for now), but the stack is cross-platform.
