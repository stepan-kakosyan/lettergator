from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from .crypto import decrypt_message, encrypt_message, is_encrypted_message


class Letter(models.Model):
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
    is_deleted = models.BooleanField(default=False)
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

    class Meta:
        ordering = ["delivery_at", "created_at"]

    def __str__(self):
        return f"Letter to {self.recipient_email} on {self.delivery_at}"

    def set_message(self, plain_text):
        self.message = encrypt_message(plain_text or "")

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
        if not self.can_delete_early or self.is_delivered or self.is_deleted:
            return False
        return timezone.now() <= self._window_deadline()

    def can_be_edited_now(self):
        if not self.can_edit_early or self.is_delivered or self.is_deleted:
            return False
        return timezone.now() <= self._window_deadline()

    @property
    def can_view_content(self):
        return self.allow_sender_preview or self.is_delivered

    @property
    def status_label(self):
        if self.is_deleted:
            return "Deleted"
        if self.has_delivery_issue:
            return "Issued"
        if self.is_delivered:
            return "Delivered"
        return "Scheduled"


class CeleryTaskLog(models.Model):
    STATUS_STARTED = "started"
    STATUS_SUCCESS = "success"
    STATUS_FAILURE = "failure"
    STATUS_CHOICES = [
        (STATUS_STARTED, "Started"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILURE, "Failure"),
    ]

    task_name = models.CharField(max_length=200)
    task_id = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_STARTED
    )
    detail = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.task_name} [{self.status}] @ {self.started_at:%Y-%m-%d %H:%M:%S}"


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
