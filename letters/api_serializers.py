from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .forms import LetterForm
from .models import Letter


class LetterListSerializer(serializers.ModelSerializer):
    recipients = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    can_be_deleted_now = serializers.SerializerMethodField()
    can_be_edited_now = serializers.SerializerMethodField()
    can_view_content = serializers.SerializerMethodField()
    delete_until = serializers.SerializerMethodField()
    edit_until = serializers.SerializerMethodField()

    class Meta:
        model = Letter
        fields = [
            "id",
            "subject",
            "send_to_me",
            "delivery_at",
            "recipients",
            "can_delete_early",
            "can_edit_early",
            "allow_sender_preview",
            "message",
            "is_delivered",
            "has_delivery_issue",
            "status_label",
            "can_be_deleted_now",
            "can_be_edited_now",
            "can_view_content",
            "delete_until",
            "edit_until",
            "created_at",
        ]

    def get_recipients(self, obj):
        return [obj.recipient_email] + list(obj.recipient_emails)

    def get_message(self, obj):
        if obj.can_view_content:
            return obj.get_message()
        return ""

    def get_can_be_deleted_now(self, obj):
        return obj.can_be_deleted_now()

    def get_can_be_edited_now(self, obj):
        return obj.can_be_edited_now()

    def get_can_view_content(self, obj):
        return obj.can_view_content

    def get_delete_until(self, obj):
        if not obj.can_delete_early:
            return None
        return obj.delete_until()

    def get_edit_until(self, obj):
        if not obj.can_edit_early:
            return None
        return obj.edit_until()


class LetterCreateSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=200)
    send_to_me = serializers.BooleanField(default=True)
    delivery_at = serializers.DateTimeField()
    can_delete_early = serializers.BooleanField(default=False)
    can_edit_early = serializers.BooleanField(default=False)
    allow_sender_preview = serializers.BooleanField(default=False)
    message = serializers.CharField()
    recipient_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        allow_empty=True,
        default=list,
    )

    def validate(self, attrs):
        user = self.context["request"].user
        form_data = {
            "subject": attrs["subject"],
            "send_to_me": attrs.get("send_to_me", True),
            "delivery_at": attrs["delivery_at"],
            "can_delete_early": attrs.get("can_delete_early", False),
            "can_edit_early": attrs.get("can_edit_early", False),
            "allow_sender_preview": attrs.get("allow_sender_preview", False),
            "message": attrs["message"],
            "recipient_list": ",".join(attrs.get("recipient_emails", [])),
        }

        form = LetterForm(data=form_data, user=user)
        if not form.is_valid():
            detail = {}
            for field, errors in form.errors.items():
                key = "non_field_errors" if field == forms.forms.NON_FIELD_ERRORS else field
                detail[key] = list(errors)
            raise serializers.ValidationError(detail)

        attrs["_bound_form"] = form
        return attrs

    def create(self, validated_data):
        form = validated_data["_bound_form"]
        try:
            return form.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {"non_field_errors": [str(exc)]}
            ) from exc


class LetterMessageUpdateSerializer(serializers.Serializer):
    message = serializers.CharField()

    def validate(self, attrs):
        letter = self.context["letter"]
        if letter.is_delivered:
            raise serializers.ValidationError(
                "Delivered letters cannot be edited."
            )
        if not letter.can_edit_early:
            raise serializers.ValidationError("Edit is disabled for this letter.")
        if timezone.now() > letter.edit_until():
            raise serializers.ValidationError("Edit window has expired for this letter.")
        return attrs


class DeliveryStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["delivered", "failed"])
