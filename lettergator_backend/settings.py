import os
from pathlib import Path
from datetime import timedelta

import pymysql
from celery.schedules import crontab
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
pymysql.install_as_MySQLdb()

load_dotenv(BASE_DIR.parent / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-key")
DEBUG = os.getenv("DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("ALLOWED_HOSTS", "*" if DEBUG else "").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "accounts",
    "letters",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "lettergator_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "lettergator_backend.wsgi.application"
ASGI_APPLICATION = "lettergator_backend.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME", "lettergator"),
        "USER": os.getenv("DB_USER", "root"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "3306"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = os.getenv("STATIC_URL", "/static/").strip() or "/static/"
if not STATIC_URL.endswith("/"):
    STATIC_URL = f"{STATIC_URL}/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_USE_FINDERS = (
    os.getenv("WHITENOISE_USE_FINDERS", "1") == "1"
)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.CustomUser"
LOGIN_REDIRECT_URL = "dashboard_view"
LOGOUT_REDIRECT_URL = "landing-page"

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "lettergator_backend.email_backend.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "0") == "1"
# Safety: Django email backend rejects both as True; prefer SSL for port 465.
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    if EMAIL_PORT == 465:
        EMAIL_USE_TLS = False
    else:
        EMAIL_USE_SSL = False
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@lettergator.local"
)
SITE_URL = os.getenv("SITE_URL", "http://localhost:8040")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

LETTER_MESSAGE_ENCRYPTION_KEY = os.getenv("LETTER_MESSAGE_ENCRYPTION_KEY", "")

ARWEAVE_KEY_FILE = os.getenv(
    "ARWEAVE_KEY_FILE", str(BASE_DIR / "arweave_key.json")
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Trust the domain when running behind an HTTPS reverse proxy
_csrf_trusted = os.getenv("CSRF_TRUSTED_ORIGINS", "").strip()
if _csrf_trusted:
    CSRF_TRUSTED_ORIGINS = [
        o.strip() for o in _csrf_trusted.split(",") if o.strip()
    ]

# Recognise HTTPS forwarded by a reverse proxy (nginx / Caddy)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

_cors_allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
if _cors_allowed_origins:
    CORS_ALLOWED_ORIGINS = [
        origin.strip()
        for origin in _cors_allowed_origins.split(",")
        if origin.strip()
    ]
else:
    CORS_ALLOW_ALL_ORIGINS = DEBUG

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    CELERY_BROKER_URL,
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "queue-due-letters-every-10-minutes": {
        "task": "letters.tasks.queue_due_letters_task",
        "schedule": crontab(minute="*/10"),
    },
    # TEMPORARY SAFETY STOP: Arweave backups are paused until manually re-enabled.
    # "queue-arweave-backups-every-10-minutes": {
    #     "task": "letters.tasks.queue_arweave_backup_task",
    #     "schedule": crontab(minute="*/10"),
    # },
    "send-email-reactivation-reminders-every-morning": {
        "task": "accounts.tasks.send_email_reactivation_reminders_task",
        "schedule": crontab(hour=8, minute=0),
    },
}
