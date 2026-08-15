"""
Django settings for SAS (Smart Attendance System) project.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.1/ref/settings/
"""

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from a .env file at the project root (if present).
load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    """Read a conventional boolean environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'true', '1', 'yes', 'on'}


def env_list(name, default=''):
    """Read a comma-separated environment variable without empty values."""
    return [value.strip() for value in os.getenv(name, default).split(',') if value.strip()]


def required_env(name):
    """Return a deployment secret or fail before the server starts."""
    value = os.getenv(name, '').strip()
    if not value:
        raise ImproperlyConfigured(f'{name} must be configured for this deployment.')
    return value


DEPLOYMENT_TARGET = os.getenv('DEPLOYMENT_TARGET', 'local').strip().lower()

DEBUG = env_bool('DJANGO_DEBUG', default=DEPLOYMENT_TARGET == 'local')

# SECURITY WARNING: keep the secret key used in production secret!
# The key is never hardcoded here so it can't leak through version control.
# In DEBUG we fall back to a throwaway key generated per process; with DEBUG
# off the key must be supplied via the environment or startup fails loudly.
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = get_random_secret_key()
    else:
        raise ImproperlyConfigured(
            'DJANGO_SECRET_KEY environment variable must be set when DEBUG is off. '
            'Generate one with: '
            'python -c "from django.core.management.utils import get_random_secret_key; '
            'print(get_random_secret_key())"'
        )


ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', '*' if DEBUG else '')
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        'DJANGO_ALLOWED_HOSTS must list the public API host when DEBUG is off.'
    )

CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')

# Hugging Face terminates TLS before forwarding requests to Gunicorn.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', default=not DEBUG)
SECURE_REDIRECT_EXEMPT = [r'^health/']
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_SECURE_HSTS_SECONDS', '0' if DEBUG else '3600'))
# Never include subdomains for a shared ``hf.space`` hostname.
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
X_FRAME_OPTIONS = 'DENY'

# Django's generic deploy check recommends HSTS for every subdomain and browser
# preload. A Space runs below the shared hf.space parent, so claiming either is
# inappropriate; all other deployment security checks remain enabled.
SILENCED_SYSTEM_CHECKS = (
    ['security.W005', 'security.W021']
    if DEPLOYMENT_TARGET == 'huggingface'
    else []
)


# Application definition

DJANGO_APPS = [
    'unfold',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'storages',
]

LOCAL_APPS = [
    'accounts',
    'organisations',
    'enrollment',
    'attendance',
    'approvals',
    'leave',
    'documents',
    'audit',
    'analytics',
    'notifications',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'SAS.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'SAS.wsgi.application'


# SQLite remains the zero-configuration local default. Hosted deployments use
# the Supabase Session Pooler connection string through ``DATABASE_URL``.
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.getenv('DATABASE_CONN_MAX_AGE', '60')),
            ssl_require=env_bool('DATABASE_SSL_REQUIRE', default=True),
        )
    }
    DATABASES['default']['CONN_HEALTH_CHECKS'] = True
    if str(DATABASES['default'].get('PORT', '')) == '6543':
        # Supavisor transaction mode does not support prepared statements or
        # server-side cursors. Session mode on port 5432 is preferred.
        DATABASES['default'].setdefault('OPTIONS', {})['prepare_threshold'] = None
        DISABLE_SERVER_SIDE_CURSORS = True
else:
    if DEPLOYMENT_TARGET == 'huggingface':
        raise ImproperlyConfigured(
            'DATABASE_URL must contain the Supabase Session Pooler URL.'
        )
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Custom user model
# Must be set before the very first migration is applied.

AUTH_USER_MODEL = 'accounts.User'


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

# Timestamps are stored in UTC; display conversion happens per user/location.
TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Local development uses ``MEDIA_ROOT``. Hugging Face has an ephemeral disk, so
# production files are sent to a private Supabase Storage bucket via its S3 API.
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

SUPABASE_STORAGE_ENABLED = env_bool(
    'SUPABASE_STORAGE_ENABLED',
    default=DEPLOYMENT_TARGET == 'huggingface',
)

STORAGES = {
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
            if DEBUG
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}

if SUPABASE_STORAGE_ENABLED:
    STORAGES['default'] = {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'access_key': required_env('SUPABASE_S3_ACCESS_KEY_ID'),
            'secret_key': required_env('SUPABASE_S3_SECRET_ACCESS_KEY'),
            'bucket_name': required_env('SUPABASE_STORAGE_BUCKET'),
            'endpoint_url': required_env('SUPABASE_S3_ENDPOINT_URL').rstrip('/'),
            'region_name': os.getenv('SUPABASE_S3_REGION', 'us-east-1'),
            'signature_version': 's3v4',
            'addressing_style': 'path',
            'default_acl': None,
            'file_overwrite': False,
            'querystring_auth': True,
            'querystring_expire': int(
                os.getenv('SUPABASE_SIGNED_URL_EXPIRY_SECONDS', '900')
            ),
            'object_parameters': {
                'CacheControl': 'private, no-store, max-age=0',
            },
        },
    }
else:
    STORAGES['default'] = {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    }

# A liveness request contains three compressed images. Documents are capped
# below Supabase Free's per-file limit and spooled to temporary disk when large.
DATA_UPLOAD_MAX_MEMORY_SIZE = int(
    os.getenv('DATA_UPLOAD_MAX_MEMORY_SIZE', str(25 * 1024 * 1024))
)
FILE_UPLOAD_MAX_MEMORY_SIZE = int(
    os.getenv('FILE_UPLOAD_MAX_MEMORY_SIZE', str(5 * 1024 * 1024))
)
FILE_UPLOAD_PERMISSIONS = 0o600
MAX_DOCUMENT_UPLOAD_BYTES = int(
    os.getenv('MAX_DOCUMENT_UPLOAD_BYTES', str(10 * 1024 * 1024))
)


# Default primary key field type
# https://docs.djangoproject.com/en/6.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

EMAIL_BACKEND = os.getenv(
    'DJANGO_EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)


# Django REST Framework
# https://www.django-rest-framework.org/api-guide/settings/

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_RENDERER_CLASSES': (
        ('rest_framework.renderers.JSONRenderer',)
        if not DEBUG
        else (
            'rest_framework.renderers.JSONRenderer',
            'rest_framework.renderers.BrowsableAPIRenderer',
        )
    ),
}


# Simple JWT
# https://django-rest-framework-simplejwt.readthedocs.io/

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}


# CORS — Flutter mobile app + React admin portal
# https://github.com/adamchainz/django-cors-headers

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS')
CORS_ALLOW_CREDENTIALS = env_bool('CORS_ALLOW_CREDENTIALS', default=False)

if DEPLOYMENT_TARGET == 'huggingface' and not CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured(
        'CORS_ALLOWED_ORIGINS must include the public Flutter web Space origin.'
    )


LOG_LEVEL = os.getenv('DJANGO_LOG_LEVEL', 'INFO').upper()
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '{asctime} {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}


# ── Smart Attendance System — domain settings ────────────────────────────
# All verification thresholds live server-side; the client never decides
# whether a check-in passes.

# Face recognition (ArcFace via ONNX Runtime)
FACE_EMBEDDING_DIM = 512
# Cosine similarity at or above this value counts as a match. Tune with real data.
FACE_MATCH_THRESHOLD = float(os.getenv('FACE_MATCH_THRESHOLD', '0.60'))
# Directory holding the downloaded .onnx model weights. The Docker image bakes
# these immutable files in so Space restarts do not depend on runtime downloads.
FACE_MODEL_DIR = Path(os.getenv('FACE_MODEL_DIR', str(BASE_DIR / 'ml_models')))
FACE_MODEL_REQUIRED_FILES = (
    'models/buffalo_l/det_10g.onnx',
    'models/buffalo_l/w600k_r50.onnx',
    'models/buffalo_l/1k3d68.onnx',
)
# Close-up mobile captures can use a smaller detector input to reduce CPU load.
FACE_DETECTION_SIZE = int(os.getenv('FACE_DETECTION_SIZE', '320'))

# Server-issued active liveness challenge.
LIVENESS_CHALLENGE_TTL_SECONDS = int(os.getenv('LIVENESS_CHALLENGE_TTL_SECONDS', '90'))
LIVENESS_STRAIGHT_MAX_YAW = float(os.getenv('LIVENESS_STRAIGHT_MAX_YAW', '12'))
LIVENESS_TURN_MIN_YAW = float(os.getenv('LIVENESS_TURN_MIN_YAW', '15'))
LIVENESS_SEQUENCE_FACE_THRESHOLD = float(
    os.getenv('LIVENESS_SEQUENCE_FACE_THRESHOLD', '0.45')
)
LIVENESS_MAX_FRAME_BYTES = int(os.getenv('LIVENESS_MAX_FRAME_BYTES', str(2 * 1024 * 1024)))
BIOMETRIC_CONSENT_VERSION = os.getenv('BIOMETRIC_CONSENT_VERSION', '2026-08-14')

# Geofencing
DEFAULT_GEOFENCE_RADIUS_METERS = int(os.getenv('DEFAULT_GEOFENCE_RADIUS_METERS', '100'))

# SAS/settings.py
from django.templatetags.static import static
UNFOLD = {
    "SITE_TITLE": "Smart Attendance Admin",
    "SITE_HEADER": "Smart Attendance System",
    # 2. Add your logo and icon paths
    "SITE_ICON": lambda request: static("images/admin-logo.png"),  # Small icon / favicon
    "SITE_LOGO": lambda request: static("images/admin-logo.png"),  # Main logo in header/sidebar
    "DASHBOARD_CALLBACK": "SAS.dashboard.custom_dashboard_callback",
    
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        
        "navigation": [
            # --- DASHBOARD LINK ---
            {
                "title": "Navigation",
                "separator": True,
                "items": [
                    {
                        "title": "Dashboard",
                        "icon": "dashboard",
                        "link": "/admin/", 
                    },
                ],
            },
            
            # --- CORE SYSTEM ---
            {
                "title": "Core System",
                "separator": True, 
                "items": [
                    {
                        "title": "Users & Accounts",
                        "icon": "people", 
                        "link": "/admin/accounts/user/",
                    },
                    {
                        "title": "Attendance Records",
                        "icon": "calendar_month",
                        "link": "/admin/attendance/attendancerecord/",
                    },
                ],
            },
            
            # --- HR & MANAGEMENT ---
            {
                "title": "HR & Management",
                "separator": True,
                "items": [
                    {
                        "title": "Leave Requests",
                        "icon": "beach_access",
                        "link": "/admin/leave/leaverequest/", 
                    },
                    {
                        "title": "Approvals",
                        "icon": "fact_check",
                        "link": "/admin/approvals/accountapprovalrequest/",
                    },
                    {
                        "title": "Document Requests",
                        "icon": "request_page",
                        "link": "/admin/documents/documentrequest/",
                    },
                    {
                        "title": "Document Review",
                        "icon": "folder_shared",
                        "link": "/admin/documents/workerdocument/",
                    },
                ]
            },
            
            # --- ANALYTICS & LOGS ---
            {
                "title": "Analytics & Logs",
                "separator": True,
                "items": [
                    {
                        "title": "Daily Summaries",
                        "icon": "bar_chart",
                        "link": "/admin/analytics/departmentdailysummary/",
                    },
                    {
                        "title": "Audit Logs",
                        "icon": "history",
                        "link": "/admin/audit/auditlog/",
                    },
                ]
            },
        ],
    },
}
