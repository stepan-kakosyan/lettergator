import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Letter

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Letter)
def enqueue_arweave_backup_in_debug(sender, instance, created, **kwargs):
    """
    Debug-only helper: enqueue Arweave backup right after a new letter commit
    so local/testing environments can verify the backup flow immediately.
    """
    if not settings.DEBUG or not created or instance.arweave_tx_id:
        return

    logger.warning(
        "Arweave backup enqueue is temporarily disabled for letter %s.",
        instance.id,
    )
