from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from .services import send_email_reactivation_email
from .services import send_pending_email_confirmation_email


@shared_task(bind=True, max_retries=5)
def send_pending_email_confirmation_task(self, user_id):
    user_model = get_user_model()
    try:
        user = user_model.objects.get(id=user_id)
    except user_model.DoesNotExist:
        return

    if not user.pending_email:
        return

    try:
        send_pending_email_confirmation_email(None, user)
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            raise
        raise self.retry(exc=exc, countdown=120)


@shared_task
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
