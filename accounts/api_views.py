from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .api_serializers import LoginSerializer, RegisterSerializer, UserSummarySerializer
from .services import send_activation_email


class RegisterApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        activation_email_sent = True
        try:
            send_activation_email(request, user)
        except Exception:
            activation_email_sent = False

        return Response(
            {
                "user": UserSummarySerializer(user).data,
                "activation_email_sent": activation_email_sent,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSummarySerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class MeApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSummarySerializer(request.user).data)


class ResendActivationApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.email_verified:
            return Response(
                {"detail": "Your email is already verified."},
                status=status.HTTP_200_OK,
            )

        try:
            send_activation_email(request, user)
        except Exception:
            return Response(
                {"detail": "Unable to resend activation email right now."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"detail": "Activation email was sent again."},
            status=status.HTTP_200_OK,
        )
