from django.urls import path

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
