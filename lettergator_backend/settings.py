import os
from pathlib import Path
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import pymysql
from dotenv import load_dotenv
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent
pymysql.install_as_MySQLdb()

load_dotenv(BASE_DIR.parent / ".env")


def _env_int(name, default):
    raw_value = os.getenv(name, str(default)).strip()
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return int(default)


def _env_decimal(name, default):
    raw_value = os.getenv(name, str(default)).strip()
    try:
        return Decimal(raw_value)
    except (TypeError, ValueError, InvalidOperation):
        return Decimal(str(default))


SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-key")
DJANGO_API_TOKEN = os.getenv("DJANGO_API_TOKEN", "")
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
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.UserLanguageMiddleware",
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
                    "django.template.context_processors.i18n",
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

LANGUAGES = [
    ("en", _("English")),
    ("ru", _("Russian")),
    ("hy", _("Armenian")),
]
LANGUAGE_CODE = "en"
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
USE_I18N = True
USE_L10N = True
LOCALE_PATHS = [BASE_DIR / "locale"]
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

MEDIA_URL = os.getenv("MEDIA_URL", "/media/").strip() or "/media/"
if not MEDIA_URL.endswith("/"):
    MEDIA_URL = f"{MEDIA_URL}/"
MEDIA_ROOT = BASE_DIR / "media"

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "")
DYNAMODB_SCHEDULES_TABLE_NAME = os.getenv(
    "DYNAMODB_SCHEDULES_TABLE_NAME",
    "LetterGator-Schedules",
)
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = "private"

if AWS_STORAGE_BUCKET_NAME:
    if "storages" not in INSTALLED_APPS:
        INSTALLED_APPS.append("storages")
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    custom_domain = os.getenv("AWS_S3_CUSTOM_DOMAIN", "").strip()
    if custom_domain:
        AWS_S3_CUSTOM_DOMAIN = custom_domain
        MEDIA_URL = f"https://{custom_domain}/"
    else:
        MEDIA_URL = (
            f"https://{AWS_STORAGE_BUCKET_NAME}.s3."
            f"{AWS_S3_REGION_NAME}.amazonaws.com/"
        )

PHYSICAL_LETTER_EXTRA_PHOTO_PRICE_USD = _env_decimal(
    "PHYSICAL_LETTER_EXTRA_PHOTO_PRICE_USD",
    "1.00",
)
PHYSICAL_LETTER_EXTRA_PAGE_PRICE_USD = _env_decimal(
    "PHYSICAL_LETTER_EXTRA_PAGE_PRICE_USD",
    "0.50",
)
PHYSICAL_LETTER_EXTRA_YEAR_PRICE_USD = _env_decimal(
    "PHYSICAL_LETTER_EXTRA_YEAR_PRICE_USD",
    "0.50",
)
PHYSICAL_LETTER_MAX_DELIVERY_YEARS = _env_int(
    "PHYSICAL_LETTER_MAX_DELIVERY_YEARS",
    10,
)
PHYSICAL_LETTER_MAX_TEXT_FILES = _env_int(
    "PHYSICAL_LETTER_MAX_TEXT_FILES",
    3,
)
PHYSICAL_LETTER_MAX_PHOTO_FILES = _env_int(
    "PHYSICAL_LETTER_MAX_PHOTO_FILES",
    3,
)
PHYSICAL_LETTER_MAX_FILE_SIZE_MB = _env_int(
    "PHYSICAL_LETTER_MAX_FILE_SIZE_MB",
    10,
)
PHYSICAL_LETTER_TEXT_CHARS_PER_PAGE = _env_int(
    "PHYSICAL_LETTER_TEXT_CHARS_PER_PAGE",
    1800,
)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.CustomUser"
LOGIN_REDIRECT_URL = "dashboard_view"
LOGOUT_REDIRECT_URL = "landing-page"

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "lettergator_backend.email_backend.EmailBackend",
)
# MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY", "")

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

ANYMAIL = {
    "MAILGUN_API_KEY": os.getenv("MAILGUN_API_KEY"),
    "MAILGUN_SENDER_DOMAIN": os.getenv(
        "MAILGUN_SENDER_DOMAIN", "lettergator.com"
    ),
    "MAILGUN_API_URL": os.getenv(
        "MAILGUN_API_URL", "https://api.eu.mailgun.net/v3"
    ),
}
# SES backend settings (used when EMAIL_BACKEND=django_ses.SESBackend)
# AWS_SES_REGION_NAME = os.getenv(
#     "AWS_SES_REGION_NAME",
#     os.getenv("AWS_S3_REGION_NAME", ""),
# )
# AWS_SES_REGION_ENDPOINT = os.getenv("AWS_SES_REGION_ENDPOINT", "")
# _aws_ses_auto_throttle_raw = os.getenv("AWS_SES_AUTO_THROTTLE", "").strip()
# if _aws_ses_auto_throttle_raw:
#     try:
#         AWS_SES_AUTO_THROTTLE = float(_aws_ses_auto_throttle_raw)
#     except ValueError:
#         AWS_SES_AUTO_THROTTLE = None
# else:
#     # Avoid ses:GetSendQuota unless explicitly enabled via env.
#     AWS_SES_AUTO_THROTTLE = None
SITE_URL = os.getenv("SITE_URL", "http://localhost:8040")

LEMONSQUEEZY_API_KEY = os.getenv("LEMONSQUEEZY_API_KEY", "")
LEMONSQUEEZY_STORE_ID = os.getenv("LEMONSQUEEZY_STORE_ID", "")
LEMONSQUEEZY_VARIANT_ID = os.getenv("LEMONSQUEEZY_VARIANT_ID", "")
LEMONSQUEEZY_WEBHOOK_SECRET = os.getenv(
    "LEMONSQUEEZY_WEBHOOK_SECRET", ""
)
LEMONSQUEEZY_API_BASE = os.getenv(
    "LEMONSQUEEZY_API_BASE", "https://api.lemonsqueezy.com"
)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

LETTER_MESSAGE_ENCRYPTION_KEY = os.getenv("LETTER_MESSAGE_ENCRYPTION_KEY", "")
DELIVERY_WORKER_TOKEN = os.getenv("DELIVERY_WORKER_TOKEN", "")

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
