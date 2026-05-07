from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db.models import Q
from django.utils import timezone

from celery import shared_task

from .models import Letter
from .utils import upload_letter_to_arweave


def _unique_emails(emails):
    unique = []
    for email in emails:
        if email and email not in unique:
            unique.append(email)
    return unique


def _creator_cc(letter):
    creator_email = ""
    if letter.user and letter.user.email:
        creator_email = letter.user.email.strip().lower()
    elif letter.sender_email:
        creator_email = letter.sender_email.strip().lower()
    return _unique_emails([creator_email])


def _deliver_letter(letter):
    user_model = get_user_model()
    message_text = letter.get_message()
    body = (
        "This message was sent from the LetterGator platform.\n\n"
        f"{message_text}"
    )
    cc_emails = _creator_cc(letter)

    target_emails = _unique_emails(
        [letter.recipient_email, *letter.recipient_emails]
    )
    if not target_emails:
        raise ValueError(f"Letter {letter.id} has no target recipients.")

    for target_email in target_emails:
        fallback_emails = []
        recipient_user = user_model.objects.filter(
            email__iexact=target_email
        ).first()
        if recipient_user:
            fallback_emails = list(
                recipient_user.secondary_emails.values_list("email", flat=True)
            )

        attempted_emails = _unique_emails([target_email, *fallback_emails])
        delivered_for_target = False

        for recipient_email in attempted_emails:
            email = EmailMessage(
                subject=letter.subject,
                body=body,
                from_email=None,
                to=[recipient_email],
                cc=cc_emails,
            )
            try:
                email.send(fail_silently=False)
                delivered_for_target = True
                break
            except Exception:
                continue

        if not delivered_for_target:
            raise RuntimeError(
                "Delivery failed for all recipients of "
                f"{target_email} for letter {letter.id}."
            )


@shared_task
def queue_due_letters_task():
    now = timezone.now()
    window_start = now - timedelta(minutes=10)
    due_letters = Letter.objects.filter(
        delivery_at__gt=window_start,
        delivery_at__lte=now,
        is_delivered=False,
        is_deleted=False,
    )

    queued_count = 0
    for letter_id in due_letters.values_list("id", flat=True):
        deliver_letter_task.delay(letter_id)
        queued_count += 1

    return queued_count


@shared_task(bind=True, max_retries=5)
def deliver_letter_task(self, letter_id):
    try:
        letter = Letter.objects.select_related("user").get(id=letter_id)
    except Letter.DoesNotExist:
        return

    if letter.is_delivered or letter.is_deleted:
        return

    try:
        _deliver_letter(letter)
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            letter.has_delivery_issue = True
            letter.save(update_fields=["has_delivery_issue"])
            raise
        raise self.retry(exc=exc, countdown=120)

    letter.is_delivered = True
    letter.has_delivery_issue = False
    letter.save(update_fields=["is_delivered", "has_delivery_issue"])


@shared_task
def queue_arweave_backup_task():
    """
    Nightly selector for Arweave backups.

    Eligibility rules:
    - No existing Arweave transaction id.
    - Letter is at least 1 year past its scheduled delivery date.
    - Skip while early edit/delete windows are still open.
    """
    now = timezone.now()
    one_year_ago = now - timedelta(days=365)
    window_closed_before = now - timedelta(days=30)

    eligible_letters = Letter.objects.filter(
        Q(arweave_tx_id__isnull=True) | Q(arweave_tx_id=""),
        delivery_at__lte=one_year_ago,
        is_deleted=False,
    ).filter(
        Q(can_edit_early=False) | Q(created_at__lte=window_closed_before),
        Q(can_delete_early=False) | Q(created_at__lte=window_closed_before),
    )

    queued_count = 0
    for letter_id in eligible_letters.values_list("id", flat=True):
        backup_letter_to_arweave_task.delay(letter_id)
        queued_count += 1

    return queued_count


@shared_task(bind=True, max_retries=5)
def backup_letter_to_arweave_task(self, letter_id):
    try:
        letter = Letter.objects.select_related("user").get(id=letter_id)
    except Letter.DoesNotExist:
        return

    if letter.arweave_tx_id:
        return

    tx_id = upload_letter_to_arweave(letter)
    if not tx_id:
        # Network failures are retried; utility remains idempotent and will
        # skip if another worker already persisted a transaction id.
        raise self.retry(countdown=300)

    Letter.objects.filter(
        pk=letter.pk,
    ).filter(
        Q(arweave_tx_id__isnull=True) | Q(arweave_tx_id=""),
    ).update(arweave_tx_id=tx_id)
