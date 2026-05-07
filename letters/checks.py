from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security)
def check_letter_encryption_key_config(app_configs, **kwargs):
    """Require explicit LETTER_MESSAGE_ENCRYPTION_KEY in production."""
    if settings.DEBUG:
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
