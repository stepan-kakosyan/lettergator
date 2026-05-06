from django.urls import path

from .views import (
    EmailLoginView,
    activate_account_view,
    logout_view,
    register_view,
    resend_activation_email_view,
)

urlpatterns = [
    path("register/", register_view, name="register"),
    path("login/", EmailLoginView.as_view(), name="login"),
    path("logout/", logout_view, name="logout"),
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
]
