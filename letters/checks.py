import sys

from django.conf import settings
from django.core.checks import Error, Tags, register

# Management commands that don't serve HTTP requests and therefore don't need
# the encryption key to be present at startup (e.g. in CI/CD pipelines).
_SKIP_COMMANDS = {
    "migrate",
    "makemigrations",
    "collectstatic",
    "shell",
    "dbshell",
    "createsuperuser",
    "test",
    "check",
    "showmigrations",
    "sqlmigrate",
    "dumpdata",
    "loaddata",
}


@register(Tags.security)
def check_letter_encryption_key_config(app_configs, **kwargs):
    """Require explicit LETTER_MESSAGE_ENCRYPTION_KEY in production."""
    if settings.DEBUG:
        return []

    # Skip during maintenance/CI commands that don't handle encrypted data.
    if len(sys.argv) >= 2 and sys.argv[1] in _SKIP_COMMANDS:
        return []

    if getattr(settings, "LETTER_MESSAGE_ENCRYPTION_KEY", "").strip():
        return []

    return [
        Error(
            "LETTER_MESSAGE_ENCRYPTION_KEY is required when DEBUG=False.",
            hint=(
                "Set LETTER_MESSAGE_ENCRYPTION_KEY in environment variables "
                "to a valid Fernet key."
            ),
            id="letters.E001",
        )
    ]
