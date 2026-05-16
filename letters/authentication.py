from django.conf import settings
from django.utils.crypto import constant_time_compare
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication


class DeliveryWorkerPrincipal:
    is_authenticated = True


class DeliveryWorkerTokenAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        expected_token = (
            getattr(settings, "DELIVERY_WORKER_TOKEN", "") or ""
        ).strip()
        if not expected_token:
            raise exceptions.AuthenticationFailed(
                "Delivery worker token is not configured."
            )

        token = self._extract_token(request)
        if not token:
            raise exceptions.AuthenticationFailed("Authentication required.")
        if not constant_time_compare(token, expected_token):
            raise exceptions.AuthenticationFailed("Invalid token.")

        return (DeliveryWorkerPrincipal(), token)

    def authenticate_header(self, request):
        return self.keyword

    def _extract_token(self, request):
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        if auth:
            parts = auth.split()
            if len(parts) == 2 and parts[0] == self.keyword:
                return parts[1].strip()

        return request.META.get("HTTP_X_API_KEY", "").strip()
