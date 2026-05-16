import logging

import boto3
from django.conf import settings
from django.utils import timezone
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)


DEFAULT_DYNAMODB_REGION = "eu-north-1"
DEFAULT_SCHEDULES_TABLE = "LetterGator-Schedules"


def _dynamodb_resource():
    region_name = (
        getattr(settings, "AWS_REGION", "")
        or getattr(settings, "AWS_S3_REGION_NAME", "")
        or DEFAULT_DYNAMODB_REGION
    )
    kwargs = {"region_name": region_name}

    access_key = getattr(settings, "AWS_ACCESS_KEY_ID", "")
    secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", "")
    if access_key and secret_key:
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key

    return boto3.resource("dynamodb", **kwargs)


def _dynamodb_region():
    return (
        getattr(settings, "AWS_REGION", "")
        or getattr(settings, "AWS_S3_REGION_NAME", "")
        or DEFAULT_DYNAMODB_REGION
    )


def _schedules_table_name():
    return getattr(
        settings,
        "DYNAMODB_SCHEDULES_TABLE_NAME",
        DEFAULT_SCHEDULES_TABLE,
    )


def _schedules_table():
    return _dynamodb_resource().Table(_schedules_table_name())


def _log_dynamodb_client_error(operation, exc):
    error = exc.response.get("Error", {})
    logger.warning(
        "DynamoDB %s failed for table %s in %s: %s - %s",
        operation,
        _schedules_table_name(),
        _dynamodb_region(),
        error.get("Code", "UnknownError"),
        error.get("Message", str(exc)),
    )


def _serialize_delivery_at(delivery_at):
    if not delivery_at:
        return ""
    if timezone.is_naive(delivery_at):
        delivery_at = timezone.make_aware(
            delivery_at,
            timezone.get_current_timezone(),
        )
    return delivery_at.isoformat()


def _status_for_letter(letter):
    if letter.has_delivery_issue:
        return "issue"
    if letter.is_delivered:
        return "delivered"
    return "scheduled"


def _all_recipients(letter):
    recipients = []
    for email in [letter.recipient_email, *letter.recipient_emails]:
        clean_email = (email or "").strip()
        if clean_email and clean_email not in recipients:
            recipients.append(clean_email)
    return recipients


def _cc_email(letter):
    if letter.user and getattr(letter.user, "email", ""):
        return (letter.user.email or "").strip().lower()
    return (letter.sender_email or "").strip().lower()


def build_schedule_item(letter):
    # Always use canonical UUID string (with hyphens) for delivery_worker_id
    import uuid
    worker_id = letter.delivery_worker_id
    if worker_id and not isinstance(worker_id, uuid.UUID):
        worker_id = uuid.UUID(str(worker_id))
    return {
        "letter_id": str(worker_id),
        "subject": letter.subject,
        "recipient": _all_recipients(letter),
        "cc_email": _cc_email(letter),
        "delivery_at": _serialize_delivery_at(letter.delivery_at),
        "status": _status_for_letter(letter),
        "message": letter.get_message(),
    }


def upsert_letter_schedule(letter):
    try:
        _schedules_table().put_item(Item=build_schedule_item(letter))
    except ClientError as exc:
        _log_dynamodb_client_error("put_item", exc)


def delete_letter_schedule(letter_id):
    try:
        _schedules_table().delete_item(Key={"letter_id": str(letter_id)})
    except ClientError as exc:
        _log_dynamodb_client_error("delete_item", exc)
