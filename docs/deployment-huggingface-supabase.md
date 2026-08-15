# Deploy AttendX with Hugging Face and Supabase

This configuration keeps the web client and APK on a lightweight Hugging Face
Static Space, runs Django and CPU face verification in a Docker Space, and
stores durable data in Supabase PostgreSQL and a private Storage bucket.

## Cost and service limits

- A Supabase Free project is suitable for the planned 4–5 presentation users.
  It currently includes a 500 MB database and 1 GB of Storage. Free projects
  with very low activity may be paused after seven days.
- Static Spaces are free. Hugging Face currently requires a paid Hub account
  to create a Docker Space, even when using the CPU Basic hardware that has no
  hourly hardware charge. Verify current pricing before creating it.
- A free Space sleeps when idle. The first API/face scan after sleep will wait
  for the container and model to start. Open `/health/ready/` before a demo.

Official references: [Hugging Face Static Spaces](https://huggingface.co/docs/hub/spaces-sdks-static),
[Docker Spaces and persistence](https://huggingface.co/docs/hub/main/spaces-sdks-docker),
[Spaces hardware](https://huggingface.co/docs/hub/spaces-overview),
[Supabase pricing](https://supabase.com/pricing), and
[Free-project pausing](https://supabase.com/docs/guides/platform/free-project-pausing).

## 1. Create Supabase persistence

1. Create a Supabase project in the region nearest the presentation venue.
2. Open **Connect**, choose **Session pooler**, and copy the PostgreSQL URI that
   uses port `5432`. Replace only the displayed password placeholder. Use the
   whole URI as `DATABASE_URL`. Session mode fits this persistent Django server;
   if transaction mode on `6543` is used, AttendX disables prepared statements
   and server-side cursors automatically.
3. In Storage, create a **private** bucket named `attendx-private`. Do not add a
   public read policy; Django generates short-lived signed URLs.
4. In Storage's S3 settings, create an S3 access-key pair and note the endpoint,
   region, access-key ID and secret key. Supabase documents its
   [S3 compatibility here](https://supabase.com/docs/guides/storage/s3/compatibility)
   and its [database connection modes here](https://supabase.com/docs/guides/database/connecting-to-postgres).

Database tables are created automatically by Django migrations when the API
Space starts. Supabase Auth is deliberately not used: the existing Django user
model and JWT endpoints remain the single authentication authority.

## 2. Create the Docker API Space

Create a Hugging Face **Docker** Space and place this repository in it. The Space
repository's root `README.md` must start with the metadata from
`deploy/huggingface/README.backend-space.md`. The root `Dockerfile` builds the
API, downloads and validates its InsightFace models, and exposes port `7860`.

Set these Space **Variables** (replace both example Space names):

```text
DEPLOYMENT_TARGET=huggingface
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourname-attendx-api.hf.space,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://yourname-attendx-api.hf.space
CORS_ALLOWED_ORIGINS=https://yourname-attendx-web.hf.space
SUPABASE_STORAGE_ENABLED=True
SUPABASE_STORAGE_BUCKET=attendx-private
SUPABASE_S3_ENDPOINT_URL=https://PROJECT_REF.storage.supabase.co/storage/v1/s3
SUPABASE_S3_REGION=YOUR_PROJECT_REGION
DATABASE_SSL_REQUIRE=True
WEB_CONCURRENCY=1
GUNICORN_THREADS=2
```

Set these values as encrypted Space **Secrets**, never Variables or committed
files:

```text
DJANGO_SECRET_KEY=<a long random value>
DATABASE_URL=<Supabase Session Pooler URI>
SUPABASE_S3_ACCESS_KEY_ID=<S3 access key>
SUPABASE_S3_SECRET_ACCESS_KEY=<S3 secret key>
DJANGO_SUPERUSER_EMAIL=<owner email>
DJANGO_SUPERUSER_PASSWORD=<long unique initial password>
```

Generate `DJANGO_SECRET_KEY` locally without printing any other secret:

```powershell
cd backend
..\venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

On each start, the container retries migrations and idempotently creates the
configured administrator. It never changes an existing administrator password
unless `DJANGO_SUPERUSER_RESET_PASSWORD=True` is deliberately set for one
restart and then removed. After the first successful administrator login,
remove `DJANGO_SUPERUSER_PASSWORD` from the Space secrets; the Supabase user
record persists and startup will simply skip bootstrap.

After the build turns **Running**, verify:

```text
https://yourname-attendx-api.hf.space/health/live/
https://yourname-attendx-api.hf.space/health/ready/
https://yourname-attendx-api.hf.space/admin/
```

`live` proves the process is responsive. `ready` additionally checks PostgreSQL
and the required face models without loading a model for every probe.

## 3. Package the web app and APK

For a proper Android release, create a private upload keystore, copy
`frontend/attendx/android/key.properties.example` to `key.properties`, and fill
in its local path/passwords. Both the keystore and real property file are
ignored by Git.

Build one deployable folder, replacing the API URL with the actual Docker Space:

```powershell
.\scripts\package_huggingface_web.ps1 `
  -ApiBaseUrl https://yourname-attendx-api.hf.space
```

For this presentation only, the existing development signing fallback can be
explicitly allowed:

```powershell
.\scripts\package_huggingface_web.ps1 `
  -ApiBaseUrl https://yourname-attendx-api.hf.space `
  -AllowDevelopmentSigning
```

The script creates `dist/huggingface-web/` containing the optimized Flutter web
build, `AttendX.apk`, and the required Static Space metadata. The browser's
**Download mobile app** button is compiled to the local `AttendX.apk` URL.

## 4. Create the Static web Space

Create a **Static** Space and upload only the contents of
`dist/huggingface-web/` to its repository root. No secrets are required: the
public API base URL is intentionally compiled into the client. Open:

```text
https://yourname-attendx-web.hf.space
```

Use HTTPS Space URLs directly so browser camera and geolocation APIs work. If
the final web Space hostname differs from the CORS value set earlier, update
`CORS_ALLOWED_ORIGINS` in the API Space and restart it.

## 5. Before the presentation

1. Confirm `/health/ready/` returns `200` and both checks are `true`.
2. Sign into `/admin/`, create the organization, departments, work location and
   the 4–5 worker accounts.
3. Open the web Space on each phone and grant camera/location permission.
4. Enrol one test account, check in/out, submit a document, and confirm its
   private upload is visible through the admin.
5. Keep Supabase database backups/export in mind before using real biometric or
   employee data. Rotate the bootstrap admin password and S3 credentials if
   they were shared during setup.
