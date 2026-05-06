import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

ENCRYPTION_PREFIX = "enc:v1:"


def _build_fernet_key():
    configured_key = getattr(settings, "LETTER_MESSAGE_ENCRYPTION_KEY", "")
    if configured_key:
        return configured_key.encode("utf-8")

    # Dev fallback so local setup works without extra env setup.
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet():
    return Fernet(_build_fernet_key())


def is_encrypted_message(value):
    return bool(value) and value.startswith(ENCRYPTION_PREFIX)


def encrypt_message(plain_text):
    token = _fernet().encrypt((plain_text or "").encode("utf-8"))
    return f"{ENCRYPTION_PREFIX}{token.decode('utf-8')}"


def decrypt_message(stored_value):
    if not stored_value:
        return ""
    if not is_encrypted_message(stored_value):
        return stored_value

    token = stored_value[len(ENCRYPTION_PREFIX):]
    try:
        plain_bytes = _fernet().decrypt(token.encode("utf-8"))
    except InvalidToken:
        return ""
    return plain_bytes.decode("utf-8")
