import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone

from .crypto import decrypt_message, is_encrypted_message
from .dynamodb_sync import delete_letter_schedule, upsert_letter_schedule


logger = logging.getLogger(__name__)


class Letter(models.Model):
    # save method is defined below with all logic
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="letters",
        null=True,
        blank=True,
    )
    subject = models.CharField(max_length=200)
    sender_email = models.EmailField()
    recipient_email = models.EmailField()
    recipient_emails = models.JSONField(default=list, blank=True)
    send_to_me = models.BooleanField(default=True)
    delivery_at = models.DateTimeField()
    can_delete_early = models.BooleanField(default=False)
    can_edit_early = models.BooleanField(default=False)
    allow_sender_preview = models.BooleanField(default=False)
    message = models.TextField()
    is_delivered = models.BooleanField(default=False)
    has_delivery_issue = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    arweave_tx_id = models.CharField(
        max_length=100, null=True, blank=True
    )
    idempotency_key = models.CharField(
        max_length=64, blank=True, default="", db_index=True
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    delivery_worker_id = models.CharField(
        max_length=36,
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    class Meta:
        ordering = ["delivery_at", "created_at"]

    def __str__(self):
        return f"Letter to {self.recipient_email} on {self.delivery_at}"

    def set_message(self, plain_text):
        self.message = plain_text or ""

    def get_message(self):
        return decrypt_message(self.message or "", letter_id=self.id)

    @property
    def message_is_encrypted(self):
        return is_encrypted_message(self.message or "")

    def _window_deadline(self):
        return self.created_at + timedelta(days=30)

    def delete_until(self):
        return self._window_deadline()

    def edit_until(self):
        return self._window_deadline()

    def can_be_deleted_now(self):
        if not self.can_delete_early or self.is_delivered:
            return False
        return timezone.now() <= self._window_deadline()

    def can_be_edited_now(self):
        if not self.can_edit_early or self.is_delivered:
            return False
        return timezone.now() <= self._window_deadline()

    @property
    def can_view_content(self):
        return self.allow_sender_preview or self.is_delivered

    @property
    def status_label(self):
        if self.has_delivery_issue:
            return "Issued"
        if self.is_delivered:
            return "Delivered"
        return "Scheduled"

    def _safe_sync_schedule_upsert(self):
        try:
            upsert_letter_schedule(self)
        except Exception:
            logger.exception(
                "Failed to upsert letter %s into DynamoDB schedules.",
                self.id,
            )

    @staticmethod
    def _safe_sync_schedule_delete(letter_id):
        try:
            delete_letter_schedule(letter_id)
        except Exception:
            logger.exception(
                "Failed to delete letter %s from DynamoDB schedules.",
                letter_id,
            )

    def _queue_schedule_upsert(self, using):
        transaction.on_commit(
            lambda: self._safe_sync_schedule_upsert(),
            using=using,
        )

    def soft_delete(self, using=None):
        self.delete()

    def save(self, *args, **kwargs):
        print(f"Saving letter with delivery_worker_id: {self.delivery_worker_id}")
        print(str(uuid.uuid4()))
        print(str(
                uuid.UUID(str(self.delivery_worker_id))
            ))
        # Ensure delivery_worker_id is always a canonical UUID
        if not self.delivery_worker_id:
            self.delivery_worker_id = str(uuid.uuid4())
        else:
            self.delivery_worker_id = str(
                uuid.UUID(str(self.delivery_worker_id))
            )
        using = kwargs.get("using") or self._state.db
        super().save(*args, **kwargs)
        self._queue_schedule_upsert(using)


@receiver(pre_delete, sender=Letter)
def remove_letter_schedule_on_delete(sender, instance, using, **kwargs):
    if not instance.id:
        return
    Letter._safe_sync_schedule_delete(instance.delivery_worker_id)


class ContactTicket(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_CLOSED, "Closed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="contact_tickets",
        null=True,
        blank=True,
    )
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} ({self.email})"


class ContactTicketComment(models.Model):
    ticket = models.ForeignKey(
        ContactTicket,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_ticket_comments",
    )
    commenter_email = models.EmailField(blank=True, default="")
    is_admin_comment = models.BooleanField(default=False)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment #{self.id} on ticket #{self.ticket_id}"


class CountryPricing(models.Model):
    country_code = models.CharField(max_length=2, unique=True)
    country_name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["country_code"]

    def save(self, *args, **kwargs):
        self.country_code = (self.country_code or "").upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.country_name} ({self.country_code})"


class PhysicalLetter(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PAID = "paid"
    STATUS_PRINTING = "printing"
    STATUS_SHIPPED = "shipped"
    STATUS_DELIVERED = "delivered"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PAID, "Paid"),
        (STATUS_PRINTING, "Printing"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_DELIVERED, "Delivered"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="physical_letters",
    )
    recipient_name = models.CharField(max_length=255)
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=120)
    state_province = models.CharField(max_length=120, blank=True, default="")
    postal_code = models.CharField(max_length=30)
    country = models.ForeignKey(
        CountryPricing,
        on_delete=models.PROTECT,
        related_name="physical_letters",
    )
    requested_delivery_date = models.DateField()
    message_text = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PAID,
    )
    tracking_number = models.CharField(max_length=100, blank=True, default="")
    total_pages = models.PositiveIntegerField(default=0)
    total_printable_pages = models.PositiveIntegerField(
        default=0, help_text="User-specified total printable pages")
    total_photos = models.PositiveIntegerField(default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Physical letter #{self.id} to {self.recipient_name} "
            f"({self.country.country_code})"
        )


class LetterAttachment(models.Model):
    TYPE_TEXT = "text"
    TYPE_PHOTO = "photo"
    TYPE_CHOICES = [
        (TYPE_TEXT, "Text"),
        (TYPE_PHOTO, "Photo"),
    ]

    physical_letter = models.ForeignKey(
        PhysicalLetter,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="physical_letters/%Y/%m/%d/")
    attachment_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    original_filename = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.get_attachment_type_display()}: {self.original_filename}"
