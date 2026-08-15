"""Small unauthenticated probes for the container platform."""

from pathlib import Path

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


def _response(payload, status=200):
    response = JsonResponse(payload, status=status)
    response['Cache-Control'] = 'no-store'
    return response


@require_GET
@never_cache
def liveness(request):
    """Confirm that Django's request loop is serving traffic."""
    return _response({'status': 'ok'})


@require_GET
@never_cache
def readiness(request):
    """Confirm that persistent data and immutable ML assets are available."""
    checks = {'database': False, 'face_models': False}

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        checks['database'] = True
    except Exception:
        # Do not expose credentials, hostnames or database exceptions publicly.
        pass

    model_root = Path(settings.FACE_MODEL_DIR)
    checks['face_models'] = all(
        (model_root / relative_path).is_file()
        for relative_path in settings.FACE_MODEL_REQUIRED_FILES
    )

    ready = all(checks.values())
    return _response(
        {'status': 'ready' if ready else 'unavailable', 'checks': checks},
        status=200 if ready else 503,
    )
