from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

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
        fields = ["full_name", "email"]


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
