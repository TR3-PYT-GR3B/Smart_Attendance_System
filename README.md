# Smart Attendance System

AttendX is organized as a small monorepo:

```text
backend/           Django API and administration dashboard
frontend/attendx/  Shared Flutter mobile and web client
scripts/           Development utilities
venv/              Existing local Python environment (kept at repository root)
```

## Backend

```powershell
cd backend
..\venv\Scripts\python.exe manage.py runserver
```

## Flutter mobile and web client

```powershell
cd frontend\attendx
flutter pub get
flutter test
flutter run -d chrome
```

Mobile and web use the same screens and API layer. Platform-specific code lives
under `frontend/attendx/lib/core/platform/`, while the standard `android/`,
`ios/`, and `web/` directories contain their respective platform runners.
