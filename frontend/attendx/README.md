# AttendX client

This Flutter package provides both the mobile application and the browser
application from one shared codebase.

## Structure

- `lib/` contains shared screens, state, routing, and API integration.
- `lib/core/platform/native/` contains native/mobile implementations.
- `lib/core/platform/web/` contains lightweight browser implementations.
- `android/` and `ios/` contain the mobile platform runners.
- `web/` contains the browser bootstrap, icons, and manifest.

## Common commands

```powershell
flutter pub get
flutter test
flutter run -d chrome
flutter build web --release `
  --dart-define=API_BASE_URL=https://your-api.example.com `
  --dart-define=MOBILE_APP_DOWNLOAD_URL=https://your-download.example.com
```
