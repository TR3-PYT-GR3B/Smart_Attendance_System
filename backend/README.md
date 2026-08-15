# AttendX backend

The backend contains the Django REST API, administration dashboard, attendance
and biometric verification services, database migrations, static files, media,
and face-model storage.

Run backend commands from this directory while using the repository-root
virtual environment:

```powershell
..\venv\Scripts\python.exe manage.py check
..\venv\Scripts\python.exe manage.py test
```

Production configuration is supplied through environment variables. The
current local database remains at `backend/db.sqlite3`; hosted deployments use
Supabase PostgreSQL and private Supabase Storage. See the repository deployment
guide for the complete Hugging Face configuration.
