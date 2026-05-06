from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .api_views import LoginApiView, MeApiView, RegisterApiView, ResendActivationApiView

urlpatterns = [
    path("register/", RegisterApiView.as_view(), name="api-register"),
    path("login/", LoginApiView.as_view(), name="api-login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="api-token-refresh"),
    path("me/", MeApiView.as_view(), name="api-me"),
    path(
        "resend-activation/",
        ResendActivationApiView.as_view(),
        name="api-resend-activation",
    ),
]
