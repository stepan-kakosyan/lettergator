import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

ENCRYPTION_PREFIX = "enc:v1:"
logger = logging.getLogger(__name__)


def _secret_key_derived_fernet():
    """Always-available fallback key derived from SECRET_KEY (used for old data)."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _fernet():
    """
    Returns a MultiFernet that tries the configured primary key first,
    then falls back to the SECRET_KEY-derived key so letters encrypted
    before LETTER_MESSAGE_ENCRYPTION_KEY was set can still be decrypted.
    In production (DEBUG=False) the primary key is required.
    """
    configured_key = getattr(settings, "LETTER_MESSAGE_ENCRYPTION_KEY", "")
    fallback = _secret_key_derived_fernet()

    if configured_key:
        primary = Fernet(configured_key.encode("utf-8"))
        return MultiFernet([primary, fallback])

    if not settings.DEBUG:
        raise ImproperlyConfigured(
            "LETTER_MESSAGE_ENCRYPTION_KEY is required when DEBUG=False."
        )

    # Dev-only: use SECRET_KEY-derived key as sole key.
    return MultiFernet([fallback])


def is_encrypted_message(value):
    return bool(value) and value.startswith(ENCRYPTION_PREFIX)


def encrypt_message(plain_text):
    token = _fernet().encrypt((plain_text or "").encode("utf-8"))
    return f"{ENCRYPTION_PREFIX}{token.decode('utf-8')}"


def decrypt_message(stored_value, letter_id=None):
    if not stored_value:
        return ""
    if not is_encrypted_message(stored_value):
        return stored_value

    token = stored_value[len(ENCRYPTION_PREFIX):]
    try:
        plain_bytes = _fernet().decrypt(token.encode("utf-8"))
    except InvalidToken:
        logger.critical(
            "Failed to decrypt letter content due to InvalidToken. "
            "letter_id=%s",
            letter_id,
            exc_info=True,
        )
        return ""
    return plain_bytes.decode("utf-8")
