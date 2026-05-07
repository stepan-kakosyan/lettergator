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

    class Meta:
        ordering = ["delivery_at", "created_at"]

    def __str__(self):
        return f"Letter to {self.recipient_email} on {self.delivery_at}"

    def set_message(self, plain_text):
        self.message = encrypt_message(plain_text or "")

    def get_message(self):
        return decrypt_message(self.message or "")

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
