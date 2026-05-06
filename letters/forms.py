from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from .models import Letter


class LetterForm(forms.ModelForm):
    recipient_list = forms.CharField(required=False, widget=forms.HiddenInput())

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

    def clean_delivery_at(self):
        delivery_at = self.cleaned_data["delivery_at"]
        if delivery_at <= timezone.now():
            raise forms.ValidationError("Delivery date and time must be in the future.")
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

        cleaned_data["_recipients"] = recipients
        cleaned_data["sender_email"] = sender_email
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user and self.user.is_authenticated:
            instance.user = self.user
        instance.sender_email = self.cleaned_data.get("sender_email", "")
        instance.set_message(self.cleaned_data.get("message", ""))
        recipients = self.cleaned_data.get("_recipients", [])
        instance.recipient_email = recipients[0]
        instance.recipient_emails = recipients[1:]

        if commit:
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
