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

## Production deployment

The production topology uses a Hugging Face Docker Space for Django, a small
Static Space for the shared Flutter web client and downloadable APK, and
Supabase for persistent PostgreSQL data and private uploads. Follow
[`docs/deployment-huggingface-supabase.md`](docs/deployment-huggingface-supabase.md).
