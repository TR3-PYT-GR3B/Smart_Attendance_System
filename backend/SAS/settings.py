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

from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from a .env file at the project root (if present).
load_dotenv(BASE_DIR / '.env')


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

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


ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',')
    if h.strip()
]


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
    'corsheaders',
    'django_filters',
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


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases
#
# NOTE: Running on SQLite for now. Geofence coordinates are stored as plain
# float columns and face embeddings as JSON, so there is no PostGIS/pgvector
# dependency. A later migration to PostgreSQL can swap in those extensions.

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

STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files (worker documents, enrolment / verification captures)
# https://docs.djangoproject.com/en/6.1/topics/files/

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Default primary key field type
# https://docs.djangoproject.com/en/6.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}


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
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
}


# Simple JWT
# https://django-rest-framework-simplejwt.readthedocs.io/

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}


# CORS — Flutter mobile app + React admin portal
# https://github.com/adamchainz/django-cors-headers

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True


# Celery — background tasks
# (face embeddings, notifications, nightly analytics aggregation)
# https://docs.celeryq.dev/

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE


# ── Smart Attendance System — domain settings ────────────────────────────
# All verification thresholds live server-side; the client never decides
# whether a check-in passes.

# Face recognition (ArcFace via ONNX Runtime)
FACE_EMBEDDING_DIM = 512
# Cosine similarity at or above this value counts as a match. Tune with real data.
FACE_MATCH_THRESHOLD = float(os.getenv('FACE_MATCH_THRESHOLD', '0.60'))
# Directory holding the downloaded .onnx model weights.
FACE_MODEL_DIR = BASE_DIR / 'ml_models'
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
