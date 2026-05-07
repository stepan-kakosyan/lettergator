from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from decimal import Decimal

from .models import CustomUser, SecondaryEmail


class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ["full_name", "email", "password1", "password2"]


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Email")

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "autocomplete": "email",
                "placeholder": "you@example.com",
            }
        )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["full_name", "email", "phone_number", "address"]


class SecondaryEmailForm(forms.ModelForm):
    class Meta:
        model = SecondaryEmail
        fields = ["email"]

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.instance.user = user

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if email == self.user.email.lower().strip():
            raise forms.ValidationError(
                "This is already your primary email address."
            )

        duplicate_exists = self.user.secondary_emails.filter(
            email__iexact=email,
        ).exclude(id=self.instance.id).exists()
        if duplicate_exists:
            raise forms.ValidationError("This email is already in your list.")

        return email

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk and self.user.secondary_emails.count() >= 5:
            raise forms.ValidationError("You can only add up to 5 emails.")
        return cleaned_data


class TestEmailForm(forms.Form):
    to_email = forms.EmailField(label="Recipient email")
    subject = forms.CharField(max_length=255)
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 6}))


class PasswordRecoveryRequestForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {
                "autocomplete": "email",
                "placeholder": "you@example.com",
                "class": (
                    "w-full border-0 border-b-2 border-gray-300 "
                    "bg-transparent px-0 py-2 focus:border-[#014421] "
                    "focus:ring-0 focus:outline-none"
                ),
            }
        )


class PasswordRecoverySetForm(SetPasswordForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields["new_password1"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "class": (
                    "w-full border-0 border-b-2 border-gray-300 "
                    "bg-transparent px-0 py-2 focus:border-[#014421] "
                    "focus:ring-0 focus:outline-none"
                ),
            }
        )
        self.fields["new_password2"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "class": (
                    "w-full border-0 border-b-2 border-gray-300 "
                    "bg-transparent px-0 py-2 focus:border-[#014421] "
                    "focus:ring-0 focus:outline-none"
                ),
            }
        )


class DashboardPasswordChangeForm(PasswordChangeForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        field_classes = (
            "w-full border-0 border-b-2 border-gray-300 bg-transparent px-0 "
            "py-2 focus:border-[#014421] focus:ring-0 focus:outline-none"
        )
        self.fields["old_password"].widget.attrs.update(
            {
                "autocomplete": "current-password",
                "class": field_classes,
            }
        )
        self.fields["new_password1"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "class": field_classes,
            }
        )
        self.fields["new_password2"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "class": field_classes,
            }
        )


class BalanceTopUpForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.50"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].widget.attrs.update(
            {
                "step": "0.50",
                "placeholder": "10.00",
                "class": (
                    "w-full border-0 border-b-2 border-gray-300 "
                    "bg-transparent px-0 py-2 focus:border-[#014421] "
                    "focus:ring-0 focus:outline-none"
                ),
            }
        )
