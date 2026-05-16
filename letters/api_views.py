from django.db import transaction
from rest_framework import permissions, status
from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.services import send_letter_created_email

from .api_serializers import (
    DeliveryStatusUpdateSerializer,
    LetterCreateSerializer,
    LetterListSerializer,
    LetterMessageUpdateSerializer,
)
from .authentication import DeliveryWorkerTokenAuthentication
from .models import Letter


class LetterListCreateApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        letters = Letter.objects.filter(user=request.user).order_by("-created_at")
        serializer = LetterListSerializer(letters, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not request.user.email_verified:
            raise PermissionDenied("Verify your email to create letters.")

        serializer = LetterCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        letter = serializer.save()

        confirmation_email_sent = True
        try:
            send_letter_created_email(request, request.user, letter)
        except Exception:
            confirmation_email_sent = False

        return Response(
            {
                "letter": LetterListSerializer(letter).data,
                "confirmation_email_sent": confirmation_email_sent,
            },
            status=status.HTTP_201_CREATED,
        )


class LetterDetailApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_letter(self, request, letter_id):
        try:
            return Letter.objects.get(id=letter_id, user=request.user)
        except Letter.DoesNotExist as exc:
            raise ValidationError("Letter not found.") from exc

    def get(self, request, letter_id):
        letter = self._get_letter(request, letter_id)
        return Response(LetterListSerializer(letter).data)

    def patch(self, request, letter_id):
        letter = self._get_letter(request, letter_id)
        serializer = LetterMessageUpdateSerializer(
            data=request.data,
            context={"letter": letter},
        )
        serializer.is_valid(raise_exception=True)

        letter.set_message(serializer.validated_data["message"])
        letter.save(update_fields=["message"])

        return Response(
            {
                "detail": "Letter text updated.",
                "letter": LetterListSerializer(letter).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, letter_id):
        letter = self._get_letter(request, letter_id)
        if letter.can_be_deleted_now():
            letter.soft_delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        if letter.can_delete_early:
            raise ValidationError("Delete window has expired for this letter.")
        raise ValidationError("Delete is disabled for this letter.")


class LetterDeliveryStatusApiView(APIView):
    authentication_classes = [DeliveryWorkerTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, letter_id):
        serializer = DeliveryStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            updated = Letter.objects.filter(
                id=int(letter_id),
            ).update(
                is_delivered=True,
                has_delivery_issue=False,
            )

        if not updated:
            raise NotFound("Letter not found.")

        return Response(status=status.HTTP_204_NO_CONTENT)
