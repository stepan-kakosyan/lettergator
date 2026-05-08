from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from accounts.models import BalanceTransaction

from .billing import (
    MIN_LONG_SCHEDULE_BALANCE_USD,
    compute_schedule_cost,
    long_schedule_cutoff,
)
from .models import ContactTicket, ContactTicketComment, Letter


class LetterForm(forms.ModelForm):
    recipient_list = forms.CharField(required=False, widget=forms.HiddenInput())
    browser_timezone = forms.CharField(required=False, widget=forms.HiddenInput())
    idempotency_key = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Letter
        fields = [
            "subject",
            "send_to_me",
            "delivery_at",
            "can_delete_early",
            "can_edit_early",
            "allow_sender_preview",
            "message",
        ]
        widgets = {
            "subject": forms.TextInput(
                attrs={
                    "placeholder": "What is this letter about?",
                    "required": True,
                }
            ),
            "delivery_at": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "required": True,
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "placeholder": "Dear future self...",
                    "rows": 6,
                    "required": True,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.user = user

        self.fields["send_to_me"].initial = True
        self.fields["can_delete_early"].initial = False
        self.fields["can_edit_early"].initial = False
        self.fields["allow_sender_preview"].initial = False

    def _get_browser_timezone(self):
        tz_name = self.data.get(self.add_prefix("browser_timezone"), "").strip()
        if not tz_name:
            return timezone.get_current_timezone_name()

        try:
            ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            return timezone.get_current_timezone_name()

        return tz_name

    def clean_delivery_at(self):
        raw_delivery_at = self.data.get(self.add_prefix("delivery_at"), "").strip()
        tz_name = self._get_browser_timezone()

        try:
            delivery_at = datetime.fromisoformat(raw_delivery_at)
        except ValueError as exc:
            raise forms.ValidationError(
                "Enter a valid delivery date and time."
            ) from exc

        if delivery_at.tzinfo is None:
            delivery_at = timezone.make_aware(delivery_at, ZoneInfo(tz_name))

        if delivery_at <= timezone.now():
            raise forms.ValidationError(
                "Delivery date and time must be in the future."
            )
        return delivery_at

    def clean(self):
        cleaned_data = super().clean()
        send_to_me = cleaned_data.get("send_to_me", True)
        sender_email = ""
        if self.user and self.user.is_authenticated and self.user.email:
            sender_email = self.user.email.strip().lower()

        if not sender_email:
            raise forms.ValidationError(
                "Sign in to create letters so we can use your account email."
            )

        recipient_list = cleaned_data.get("recipient_list", "")

        recipients = []
        if send_to_me:
            recipients = [sender_email] if sender_email else []
        else:
            raw_emails = [
                value.strip().lower()
                for value in recipient_list.split(",")
                if value.strip()
            ]
            unique_emails = []
            for email in raw_emails:
                if email not in unique_emails:
                    unique_emails.append(email)
            recipients = unique_emails

        if not recipients:
            raise forms.ValidationError(
                "Add at least one recipient email or keep 'Send to me' enabled."
            )
        if len(recipients) > 5:
            raise forms.ValidationError("You can add a maximum of 5 recipient emails.")

        for email in recipients:
            try:
                validate_email(email)
            except ValidationError:
                raise forms.ValidationError(f"Invalid email: {email}")

        delivery_at = cleaned_data.get("delivery_at")
        balance = Decimal("0.00")
        if self.user and self.user.is_authenticated:
            balance = self.user.balance

        if delivery_at and delivery_at.date() >= long_schedule_cutoff():
            if balance < MIN_LONG_SCHEDULE_BALANCE_USD:
                raise forms.ValidationError(
                    "Top up to at least $1.00 to unlock 1 year+ scheduling."
                )

        schedule_cost = Decimal("0.00")
        if delivery_at:
            schedule_cost = compute_schedule_cost(delivery_at)
        if schedule_cost > balance:
            raise forms.ValidationError(
                "Insufficient balance for this schedule. "
                f"Required: ${schedule_cost:.2f}. "
                f"Available: ${balance:.2f}."
            )

        cleaned_data["_recipients"] = recipients
        cleaned_data["sender_email"] = sender_email
        cleaned_data["_schedule_cost"] = schedule_cost
        return cleaned_data

    def save(self, commit=True):
        ikey = self.cleaned_data.get("idempotency_key", "").strip()
        existing = None
        if ikey and self.user and self.user.is_authenticated:
            existing = (
                Letter.objects.filter(
                    user=self.user,
                    idempotency_key=ikey,
                    is_delivered=False,
                    is_deleted=False,
                ).first()
            )

        if existing:
            instance = existing
        else:
            instance = super().save(commit=False)

        if self.user and self.user.is_authenticated:
            instance.user = self.user
        instance.sender_email = self.cleaned_data.get("sender_email", "")
        instance.set_message(self.cleaned_data.get("message", ""))
        recipients = self.cleaned_data.get("_recipients", [])
        instance.recipient_email = recipients[0]
        instance.recipient_emails = recipients[1:]
        if ikey:
            instance.idempotency_key = ikey
        # Copy over model fields from cleaned data when updating an existing record
        if existing:
            for field in [
                "subject", "send_to_me", "delivery_at",
                "can_delete_early", "can_edit_early", "allow_sender_preview",
            ]:
                setattr(instance, field, self.cleaned_data[field])

        if commit:
            schedule_cost = self.cleaned_data.get("_schedule_cost", Decimal("0.00"))
            with transaction.atomic():
                if (
                    schedule_cost > 0
                    and self.user
                    and self.user.is_authenticated
                ):
                    locked_user = get_user_model().objects.select_for_update().get(
                        pk=self.user.pk
                    )
                    if locked_user.balance < schedule_cost:
                        raise forms.ValidationError(
                            "Insufficient balance for this schedule. "
                            f"Required: ${schedule_cost:.2f}. "
                            f"Available: ${locked_user.balance:.2f}."
                        )
                    locked_user.balance -= schedule_cost
                    locked_user.save(update_fields=["balance"])
                    self.user.balance = locked_user.balance
                    BalanceTransaction.objects.create(
                        user=locked_user,
                        amount=-schedule_cost,
                        reason=(
                            "Letter scheduling charge "
                            f"for '{instance.subject[:80]}'"
                        ),
                    )
                    instance.user = locked_user

                instance.save()
        return instance


class LetterMessageEditForm(forms.Form):
    message = forms.CharField(
        required=True,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "required": True,
            }
        ),
    )


class ContactTicketForm(forms.ModelForm):
    class Meta:
        model = ContactTicket
        fields = ["email", "subject", "message"]
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "you@example.com",
                    "autocomplete": "email",
                }
            ),
            "subject": forms.TextInput(
                attrs={
                    "placeholder": "What do you need help with?",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "placeholder": "Describe your issue or question.",
                    "rows": 5,
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        base_input_classes = (
            "w-full border-0 border-b-2 border-gray-300 bg-transparent px-0 "
            "py-2 focus:border-[#014421] focus:ring-0 focus:outline-none"
        )
        self.fields["subject"].widget.attrs.update({"class": base_input_classes})
        self.fields["message"].widget.attrs.update(
            {
                "class": (
                    "w-full border border-gray-300 rounded-lg bg-transparent px-3 "
                    "py-2 text-sm focus:border-[#014421] focus:ring-0 "
                    "focus:outline-none resize-none"
                )
            }
        )

        if self.user and self.user.is_authenticated:
            self.fields["email"].required = False
            self.fields["email"].widget = forms.HiddenInput()
        else:
            self.fields["email"].required = True
            self.fields["email"].widget.attrs.update({"class": base_input_classes})

    def clean_email(self):
        if self.user and self.user.is_authenticated:
            return self.user.email.strip().lower()
        email = self.cleaned_data["email"].strip().lower()
        return email


class ContactTicketCommentForm(forms.ModelForm):
    class Meta:
        model = ContactTicketComment
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Add a comment...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message"].widget.attrs.update(
            {
                "class": (
                    "w-full border border-gray-300 rounded-lg bg-transparent px-3 "
                    "py-2 text-sm focus:border-[#014421] focus:ring-0 "
                    "focus:outline-none resize-none"
                )
            }
        )
