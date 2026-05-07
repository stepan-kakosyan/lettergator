from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .forms import PasswordRecoveryRequestForm, PasswordRecoverySetForm
from .views import (
    EmailLoginView,
    activate_account_view,
    confirm_pending_email_view,
    logout_view,
    register_view,
    resend_activation_email_view,
    resend_pending_email_confirmation_view,
    test_email_view,
)

urlpatterns = [
    path("register/", register_view, name="register"),
    path("login/", EmailLoginView.as_view(), name="login"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name=(
                "accounts/emails/password_reset_email.txt"
            ),
            html_email_template_name=(
                "accounts/emails/password_reset_email.html"
            ),
            subject_template_name=(
                "accounts/emails/password_reset_subject.txt"
            ),
            success_url=reverse_lazy("password_reset_done"),
            form_class=PasswordRecoveryRequestForm,
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            form_class=PasswordRecoverySetForm,
            success_url=reverse_lazy("login"),
        ),
        name="password_reset_confirm",
    ),
    path("logout/", logout_view, name="logout"),
    path("test-email/", test_email_view, name="test-email"),
    path(
        "activate/<uidb64>/<token>/",
        activate_account_view,
        name="activate-account",
    ),
    path(
        "resend-activation/",
        resend_activation_email_view,
        name="resend-activation-email",
    ),
    path(
        "resend-pending-email-confirmation/",
        resend_pending_email_confirmation_view,
        name="resend-pending-email-confirmation",
    ),
    path(
        "confirm-email-change/<uidb64>/<token>/",
        confirm_pending_email_view,
        name="confirm-pending-email",
    ),
]
