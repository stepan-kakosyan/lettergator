from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from .services import send_email_reactivation_email
from .services import send_pending_email_confirmation_email


def send_pending_email_confirmation_task(user_id, base_url=None):
    user_model = get_user_model()
    try:
        user = user_model.objects.get(id=user_id)
    except user_model.DoesNotExist:
        return

    if not user.pending_email:
        return

    send_pending_email_confirmation_email(None, user, base_url=base_url)


def send_email_reactivation_reminders_task():
    user_model = get_user_model()
    now = timezone.now()
    cutoff = now - timedelta(days=365)

    users = user_model.objects.filter(
        is_active=True,
    ).exclude(email="").filter(
        Q(email_verified_at__isnull=True) | Q(email_verified_at__lt=cutoff),
    ).filter(
        Q(email_reactivation_sent_at__isnull=True)
        | Q(email_reactivation_sent_at__lt=cutoff),
    )

    sent_count = 0
    for user in users:
        try:
            send_email_reactivation_email(user)
            user.email_reactivation_sent_at = now
            user.save(update_fields=["email_reactivation_sent_at"])
            sent_count += 1
        except Exception:
            continue

    return sent_count
