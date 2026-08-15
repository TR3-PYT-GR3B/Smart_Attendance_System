#!/bin/sh
set -eu

attempt=1
max_attempts="${MIGRATION_MAX_ATTEMPTS:-6}"

while ! python manage.py migrate --noinput; do
    if [ "$attempt" -ge "$max_attempts" ]; then
        echo "Database migration failed after $attempt attempts." >&2
        exit 1
    fi
    echo "Database is not ready; retrying migration ($attempt/$max_attempts)." >&2
    attempt=$((attempt + 1))
    sleep 5
done

if [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    python manage.py ensure_admin
fi

exec gunicorn SAS.wsgi:application \
    --bind "0.0.0.0:${PORT:-7860}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --worker-class gthread \
    --threads "${GUNICORN_THREADS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-180}" \
    --graceful-timeout 30 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    --forwarded-allow-ips='*'
