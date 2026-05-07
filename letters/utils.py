import logging
import time

import arweave
from django.conf import settings

logger = logging.getLogger(__name__)


def _response_is_success(response):
    """Handle both requests.Response-like and simple return values."""
    status_code = getattr(response, "status_code", None)
    if status_code is not None:
        return status_code in (200, 201, 202)
    if response is True:
        return True
    return False


def _response_error_text(response):
    text = getattr(response, "text", "")
    return text[:500] if text else ""


def upload_letter_to_arweave(letter):
    """
    Upload the encrypted message of *letter* to Arweave and return the
    transaction ID, or None on failure.

    Safety guarantees:
    - If letter.arweave_tx_id is already set the upload is skipped so
      re-running the signal (e.g. on retry) never double-uploads.
    - Network / signing errors are caught and logged; callers receive
      None rather than an exception so the main save flow is unaffected.
    """
    if letter.arweave_tx_id:
        logger.info(
            "Letter %s already backed up (tx %s), skipping.",
            letter.id,
            letter.arweave_tx_id,
        )
        return letter.arweave_tx_id

    # Re-check from DB in case this instance is stale during retry flows.
    if letter.id:
        from .models import Letter

        current_tx_id = (
            Letter.objects.filter(pk=letter.id)
            .values_list("arweave_tx_id", flat=True)
            .first()
        )
        if current_tx_id:
            logger.info(
                "Letter %s already has tx %s in DB, skipping upload.",
                letter.id,
                current_tx_id,
            )
            return current_tx_id

    key_path = str(
        getattr(settings, "ARWEAVE_KEY_FILE", settings.BASE_DIR / "arweave_key.json")
    )

    max_attempts = int(getattr(settings, "ARWEAVE_UPLOAD_MAX_ATTEMPTS", 3))
    retry_delay = float(getattr(settings, "ARWEAVE_UPLOAD_RETRY_DELAY", 1.5))

    try:
        wallet = arweave.Wallet(key_path)
        data = (letter.message or "").encode("utf-8")

        # Build/sign once so retries keep the same tx id.
        transaction = arweave.Transaction(wallet, data=data)
        transaction.add_tag("Content-Type", "text/plain")
        transaction.add_tag("App-Name", "Lettergator")
        transaction.add_tag("Letter-Id", str(letter.id))
        transaction.sign()

        for attempt in range(1, max_attempts + 1):
            response = transaction.send()
            if _response_is_success(response):
                tx_id = transaction.id
                logger.info(
                    "Letter %s backed up to Arweave (tx %s).",
                    letter.id,
                    tx_id,
                )
                return tx_id

            logger.warning(
                (
                    "Arweave upload attempt %s/%s failed for letter %s. "
                    "status=%s error=%s"
                ),
                attempt,
                max_attempts,
                letter.id,
                getattr(response, "status_code", "unknown"),
                _response_error_text(response),
            )

            if attempt < max_attempts:
                time.sleep(retry_delay * attempt)

        logger.error(
            "Arweave upload failed after %s attempts for letter %s.",
            max_attempts,
            letter.id,
        )
        return None
    except Exception:
        logger.exception(
            "Unexpected error uploading letter %s to Arweave.", letter.id
        )
        return None
