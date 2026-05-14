from datetime import datetime
from decimal import Decimal
import logging
import math
import re
from io import TextIOWrapper
from zipfile import BadZipFile, ZipFile
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from django.conf import settings
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import BalanceTransaction

from .billing import (
    MIN_LONG_SCHEDULE_BALANCE_USD,
    compute_schedule_cost,
    long_schedule_cutoff,
)
from .models import ContactTicket, ContactTicketComment, Letter
from .models import CountryPricing, LetterAttachment, PhysicalLetter


logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - fallback if dependency is missing.
    PdfReader = None


MAX_TEXT_FILES = settings.PHYSICAL_LETTER_MAX_TEXT_FILES
MAX_PHOTO_FILES = settings.PHYSICAL_LETTER_MAX_PHOTO_FILES
MAX_FILE_SIZE_MB = settings.PHYSICAL_LETTER_MAX_FILE_SIZE_MB
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024
EXTRA_PHOTO_PRICE_USD = settings.PHYSICAL_LETTER_EXTRA_PHOTO_PRICE_USD
EXTRA_PAGE_PRICE_USD = settings.PHYSICAL_LETTER_EXTRA_PAGE_PRICE_USD
EXTRA_YEAR_PRICE_USD = settings.PHYSICAL_LETTER_EXTRA_YEAR_PRICE_USD
MAX_DELIVERY_YEARS = settings.PHYSICAL_LETTER_MAX_DELIVERY_YEARS
TEXT_CHARS_PER_PAGE = settings.PHYSICAL_LETTER_TEXT_CHARS_PER_PAGE

TEXT_FILE_EXTENSIONS = {".pdf", ".txt", ".docx"}
PHOTO_FILE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

TEXT_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.document",
}
PHOTO_CONTENT_TYPES = {"image/jpeg", "image/png"}


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


def _safe_replace_year(value, year):
    try:
        return value.replace(year=year)
    except ValueError:
        return value.replace(month=2, day=28, year=year)


def _year_charge_count(target_date, today=None):
    current = today or timezone.now().date()
    if target_date <= current:
        return 0
    years = target_date.year - current.year
    candidate = _safe_replace_year(current, current.year + years)
    if candidate < target_date:
        years += 1
    return max(years, 0)


def _file_extension(uploaded_file):
    name = uploaded_file.name or ""
    dot_pos = name.rfind(".")
    if dot_pos < 0:
        return ""
    return name[dot_pos:].lower()


def _message_page_count(message_text):
    if not (message_text or "").strip():
        return 0
    return int(math.ceil(len(message_text.strip()) / TEXT_CHARS_PER_PAGE))


def _txt_page_count(uploaded_file):
    uploaded_file.seek(0)
    text_reader = TextIOWrapper(uploaded_file.file, encoding="utf-8", errors="ignore")
    content = text_reader.read()
    uploaded_file.seek(0)
    if not content:
        return 1
    return int(math.ceil(len(content) / TEXT_CHARS_PER_PAGE))


def _docx_page_count(uploaded_file):
    uploaded_file.seek(0)
    try:
        with ZipFile(uploaded_file.file) as archive:
            xml_data = archive.read("word/document.xml").decode("utf-8", "ignore")
    except (KeyError, BadZipFile):
        uploaded_file.seek(0)
        return 1
    uploaded_file.seek(0)
    plain_text = re.sub(r"<[^>]+>", "", xml_data)
    if not plain_text.strip():
        return 1
    return int(math.ceil(len(plain_text) / TEXT_CHARS_PER_PAGE))


def _pdf_page_count(uploaded_file):
    if PdfReader is None:
        return 1
    uploaded_file.seek(0)
    try:
        reader = PdfReader(uploaded_file.file)
        page_count = len(reader.pages)
    except Exception:  # pragma: no cover - damaged PDFs fallback to 1 page.
        uploaded_file.seek(0)
        return 1
    uploaded_file.seek(0)
    return max(page_count, 1)


def _text_file_page_count(uploaded_file):
    extension = _file_extension(uploaded_file)
    if extension == ".pdf":
        return _pdf_page_count(uploaded_file)
    if extension == ".docx":
        return _docx_page_count(uploaded_file)
    return _txt_page_count(uploaded_file)


def compute_physical_letter_total(country, pages, photos, requested_delivery_date):
    years = _year_charge_count(requested_delivery_date)
    total = country.price
    total += EXTRA_PAGE_PRICE_USD * Decimal(pages)
    total += EXTRA_PHOTO_PRICE_USD * Decimal(photos)
    total += EXTRA_YEAR_PRICE_USD * Decimal(years)
    return total.quantize(Decimal("0.01"))


class LetterForm(forms.ModelForm):
    recipient_list = forms.CharField(required=False, widget=forms.HiddenInput())
    browser_timezone = forms.CharField(required=False, widget=forms.HiddenInput())
    idempotency_key = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Letter
        fields = [
            "subject",
            "send_to_me",
            "delivery_at",
            "can_delete_early",
            "can_edit_early",
            "allow_sender_preview",
            "message",
        ]
        widgets = {
            "subject": forms.TextInput(
                attrs={
                    "placeholder": "What is this letter about?",
                    "required": True,
                }
            ),
            "delivery_at": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "required": True,
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "placeholder": "Dear future self...",
                    "rows": 6,
                    "required": True,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.user = user

        if not (self.instance and self.instance.pk):
            self.fields["send_to_me"].initial = True
            self.fields["can_delete_early"].initial = False
            self.fields["can_edit_early"].initial = False
            self.fields["allow_sender_preview"].initial = False

        if self.instance and self.instance.pk and not self.is_bound:
            self.initial["message"] = self.instance.get_message()
            local_delivery = timezone.localtime(self.instance.delivery_at)
            self.initial["delivery_at"] = local_delivery.strftime(
                "%Y-%m-%dT%H:%M"
            )
            if not self.instance.send_to_me:
                recipients = [self.instance.recipient_email]
                recipients.extend(self.instance.recipient_emails or [])
                self.initial["recipient_list"] = ",".join(
                    item for item in recipients if item
                )

    def _get_browser_timezone(self):
        tz_name = self.data.get(self.add_prefix("browser_timezone"), "").strip()
        if not tz_name:
            return timezone.get_current_timezone_name()

        try:
            ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            return timezone.get_current_timezone_name()

        return tz_name

    def clean_delivery_at(self):
        raw_delivery_at = self.data.get(self.add_prefix("delivery_at"), "").strip()
        tz_name = self._get_browser_timezone()

        try:
            delivery_at = datetime.fromisoformat(raw_delivery_at)
        except ValueError as exc:
            raise forms.ValidationError(
                "Enter a valid delivery date and time."
            ) from exc

        if delivery_at.tzinfo is None:
            delivery_at = timezone.make_aware(delivery_at, ZoneInfo(tz_name))

        if delivery_at <= timezone.now():
            raise forms.ValidationError(
                "Delivery date and time must be in the future."
            )
        return delivery_at

    def clean(self):
        cleaned_data = super().clean()
        send_to_me = cleaned_data.get("send_to_me", True)
        sender_email = ""
        if self.user and self.user.is_authenticated and self.user.email:
            sender_email = self.user.email.strip().lower()

        if not sender_email:
            raise forms.ValidationError(
                "Sign in to create letters so we can use your account email."
            )

        recipient_list = cleaned_data.get("recipient_list", "")

        recipients = []
        if send_to_me:
            recipients = [sender_email] if sender_email else []
        else:
            raw_emails = [
                value.strip().lower()
                for value in recipient_list.split(",")
                if value.strip()
            ]
            unique_emails = []
            for email in raw_emails:
                if email not in unique_emails:
                    unique_emails.append(email)
            recipients = unique_emails

        if not recipients:
            raise forms.ValidationError(
                "Add at least one recipient email or keep 'Send to me' enabled."
            )
        if len(recipients) > 5:
            raise forms.ValidationError("You can add a maximum of 5 recipient emails.")

        for email in recipients:
            try:
                validate_email(email)
            except ValidationError:
                raise forms.ValidationError(f"Invalid email: {email}")

        delivery_at = cleaned_data.get("delivery_at")
        balance = Decimal("0.00")
        if self.user and self.user.is_authenticated:
            balance = self.user.balance

        if delivery_at and delivery_at.date() >= long_schedule_cutoff():
            if balance < MIN_LONG_SCHEDULE_BALANCE_USD:
                raise forms.ValidationError(
                    "Top up to at least $1.00 to unlock 1 year+ scheduling."
                )

        schedule_cost = Decimal("0.00")
        if delivery_at:
            schedule_cost = compute_schedule_cost(delivery_at)
        original_total_price = Decimal("0.00")
        if self.instance and self.instance.pk:
            original_total_price = self.instance.total_price or Decimal("0.00")

        required_amount = schedule_cost
        if self.instance and self.instance.pk:
            required_amount = max(
                schedule_cost - original_total_price,
                Decimal("0.00"),
            )

        if required_amount > balance:
            raise forms.ValidationError(
                "Insufficient balance for this schedule. "
                f"Required: ${required_amount:.2f}. "
                f"Available: ${balance:.2f}."
            )

        cleaned_data["_recipients"] = recipients
        cleaned_data["sender_email"] = sender_email
        cleaned_data["_schedule_cost"] = schedule_cost
        cleaned_data["_required_amount"] = required_amount
        cleaned_data["_adjustment_amount"] = schedule_cost - original_total_price
        return cleaned_data

    def save(self, commit=True):
        ikey = self.cleaned_data.get("idempotency_key", "").strip()
        existing = None
        if (
            ikey
            and self.user
            and self.user.is_authenticated
            and not (self.instance and self.instance.pk)
        ):
            existing = (
                Letter.objects.filter(
                    user=self.user,
                    idempotency_key=ikey,
                    is_delivered=False,
                    is_deleted=False,
                ).first()
            )

        if existing:
            instance = existing
        else:
            instance = super().save(commit=False)

        if self.user and self.user.is_authenticated:
            instance.user = self.user
        instance.sender_email = self.cleaned_data.get("sender_email", "")
        instance.set_message(self.cleaned_data.get("message", ""))
        recipients = self.cleaned_data.get("_recipients", [])
        instance.recipient_email = recipients[0]
        instance.recipient_emails = recipients[1:]
        if ikey:
            instance.idempotency_key = ikey
        # Copy over model fields from cleaned data when updating an existing record
        if existing:
            for field in [
                "subject", "send_to_me", "delivery_at",
                "can_delete_early", "can_edit_early", "allow_sender_preview",
            ]:
                setattr(instance, field, self.cleaned_data[field])

        if commit:
            schedule_cost = self.cleaned_data.get("_schedule_cost", Decimal("0.00"))
            adjustment_amount = self.cleaned_data.get(
                "_adjustment_amount",
                schedule_cost,
            )
            with transaction.atomic():
                if self.user and self.user.is_authenticated and adjustment_amount != 0:
                    locked_user = get_user_model().objects.select_for_update().get(
                        pk=self.user.pk
                    )
                    if adjustment_amount > 0 and locked_user.balance < adjustment_amount:
                        raise forms.ValidationError(
                            "Insufficient balance for this schedule. "
                            f"Required: ${adjustment_amount:.2f}. "
                            f"Available: ${locked_user.balance:.2f}."
                        )

                    if adjustment_amount > 0:
                        locked_user.balance -= adjustment_amount
                        transaction_type = BalanceTransaction.TYPE_DEBIT
                        transaction_amount = -adjustment_amount
                    else:
                        refund_amount = -adjustment_amount
                        locked_user.balance += refund_amount
                        transaction_type = BalanceTransaction.TYPE_CREDIT
                        transaction_amount = refund_amount

                    locked_user.save(update_fields=["balance"])
                    self.user.balance = locked_user.balance
                    BalanceTransaction.objects.create(
                        user=locked_user,
                        amount=transaction_amount,
                        transaction_type=transaction_type,
                        reason=(
                            "Email letter scheduling adjustment "
                            f"for '{instance.subject[:80]}'"
                        ),
                    )
                    instance.user = locked_user

                instance.total_price = schedule_cost

                instance.save()
        return instance


class PhysicalLetterCreateForm(forms.ModelForm):
    text_files = forms.Field(
        required=False,
        widget=MultiFileInput(
            attrs={
                "accept": ".pdf,.txt,.docx",
            }
        ),
    )
    photo_files = forms.Field(
        required=False,
        widget=MultiFileInput(
            attrs={
                "accept": ".jpg,.jpeg,.png",
            }
        ),
    )
    total_printable_pages = forms.IntegerField(
        required=False,
        min_value=0,
        label="Total printable pages",
        help_text=(
            "Enter the number of pages to be printed "
            "(including all text and file uploads)"
        ),
    )

    class Meta:
        model = PhysicalLetter
        fields = [
            "recipient_name",
            "street_address",
            "city",
            "state_province",
            "postal_code",
            "country",
            "requested_delivery_date",
            "message_text",
            "total_printable_pages",
        ]
        widgets = {
            "requested_delivery_date": forms.DateInput(
                attrs={"type": "date"}
            ),
            "message_text": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.save_as_draft = kwargs.pop("save_as_draft", False)
        super().__init__(*args, **kwargs)
        self.fields["country"].queryset = CountryPricing.objects.all()

    def clean_requested_delivery_date(self):
        requested_date = self.cleaned_data["requested_delivery_date"]
        today = timezone.now().date()
        latest_date = _safe_replace_year(today, today.year + MAX_DELIVERY_YEARS)
        if requested_date < today:
            raise forms.ValidationError("Delivery date cannot be in the past.")
        if requested_date > latest_date:
            raise forms.ValidationError(
                "Delivery date must be within "
                f"{MAX_DELIVERY_YEARS} years from today."
            )
        return requested_date

    def _validate_upload(self, uploaded_file, expected_type):
        extension = _file_extension(uploaded_file)
        content_type = (uploaded_file.content_type or "").lower()
        if uploaded_file.size > MAX_FILE_SIZE:
            raise forms.ValidationError(
                f"File '{uploaded_file.name}' exceeds "
                f"{MAX_FILE_SIZE_MB}MB limit."
            )

        if expected_type == LetterAttachment.TYPE_TEXT:
            if extension not in TEXT_FILE_EXTENSIONS:
                raise forms.ValidationError(
                    f"File '{uploaded_file.name}' has an unsupported text format."
                )
            if content_type and content_type not in TEXT_CONTENT_TYPES:
                raise forms.ValidationError(
                    f"File '{uploaded_file.name}' has an invalid content type."
                )
            return

        if extension not in PHOTO_FILE_EXTENSIONS:
            raise forms.ValidationError(
                f"File '{uploaded_file.name}' has an unsupported image format."
            )
        if content_type and content_type not in PHOTO_CONTENT_TYPES:
            raise forms.ValidationError(
                f"File '{uploaded_file.name}' has an invalid content type."
            )

    def _get_uploaded_files(self, field_name):
        files = list(self.files.getlist(field_name))
        if not files:
            files = list(self.files.getlist(f"{field_name}[]"))

        if files:
            return files

        fallback = self.cleaned_data.get(field_name)
        if not fallback:
            return []
        if isinstance(fallback, (list, tuple)):
            return list(fallback)
        return [fallback]

    def _save_attachment(self, physical_letter, uploaded_file, attachment_type):
        attachment = LetterAttachment(
            physical_letter=physical_letter,
            attachment_type=attachment_type,
            original_filename=uploaded_file.name,
        )
        try:
            # Explicit save ensures the storage backend (e.g. S3) is invoked.
            attachment.file.save(uploaded_file.name, uploaded_file, save=False)
            attachment.save()
            return attachment
        except Exception:
            logger.exception(
                "Attachment save failed: letter_id=%s type=%s filename=%s",
                getattr(physical_letter, "id", None),
                attachment_type,
                getattr(uploaded_file, "name", "(unknown)"),
            )
            raise forms.ValidationError(
                f"Failed to save uploaded file '{uploaded_file.name}'."
            )

    def clean(self):
        cleaned_data = super().clean()
        text_files = self._get_uploaded_files("text_files")
        photo_files = self._get_uploaded_files("photo_files")
        deleted_attachment_ids = self.data.getlist("delete_attachment_ids")
        message_text = cleaned_data.get("message_text", "")
        country = cleaned_data.get("country")
        requested_date = cleaned_data.get("requested_delivery_date")
        existing_text_count = 0
        existing_photo_count = 0
        deleted_id_set = set()
        existing_attachments_qs = LetterAttachment.objects.none()

        if self.instance and self.instance.pk:
            for raw_id in deleted_attachment_ids:
                try:
                    deleted_id_set.add(int(raw_id))
                except (TypeError, ValueError):
                    continue

            existing_attachments_qs = self.instance.attachments.exclude(
                id__in=deleted_id_set
            )
            existing_text_count = existing_attachments_qs.filter(
                attachment_type=LetterAttachment.TYPE_TEXT
            ).count()
            existing_photo_count = existing_attachments_qs.filter(
                attachment_type=LetterAttachment.TYPE_PHOTO
            ).count()

        if existing_text_count + len(text_files) > MAX_TEXT_FILES:
            raise forms.ValidationError("You can upload up to 3 text files.")
        if existing_photo_count + len(photo_files) > MAX_PHOTO_FILES:
            raise forms.ValidationError("You can upload up to 3 photos.")

        for text_file in text_files:
            self._validate_upload(text_file, LetterAttachment.TYPE_TEXT)
        for photo_file in photo_files:
            self._validate_upload(photo_file, LetterAttachment.TYPE_PHOTO)

        if (
            not message_text.strip()
            and not text_files
            and not photo_files
            and existing_text_count == 0
            and existing_photo_count == 0
        ):
            raise forms.ValidationError(
                "Provide message text or upload at least one file."
            )

        logger.info(
            "PhysicalLetter uploads received: text=%s photo=%s keys=%s",
            len(text_files),
            len(photo_files),
            list(self.files.keys()),
        )

        total_photos = existing_photo_count + len(photo_files)
        total_printable_pages = cleaned_data.get("total_printable_pages")
        if total_printable_pages in (None, ""):
            total_printable_pages = 0
        total_printable_pages = int(total_printable_pages)

        if not country or not requested_date:
            return cleaned_data

        total_price = compute_physical_letter_total(
            country=country,
            pages=total_printable_pages,
            photos=total_photos,
            requested_delivery_date=requested_date,
        )

        submitted_action = (self.data.get("action") or "").strip().lower()
        is_pay_action = submitted_action == "pay"
        is_draft_action = submitted_action == "draft"

        if is_pay_action and self.user and self.user.balance < total_price:
            raise forms.ValidationError(
                "Insufficient balance. Required: "
                f"${total_price:.2f}. Available: ${self.user.balance:.2f}."
            )

        if (
            is_draft_action
            and self.user
            and self.instance
            and self.instance.pk
            and self.instance.status == PhysicalLetter.STATUS_PAID
        ):
            old_total_price = self.instance.total_price or Decimal("0.00")
            required_amount = max(total_price - old_total_price, Decimal("0.00"))
            if self.user.balance < required_amount:
                raise forms.ValidationError(
                    "Insufficient balance for this update. "
                    f"Need ${required_amount:.2f}, available ${self.user.balance:.2f}."
                )
            cleaned_data["_adjustment_amount"] = total_price - old_total_price

        cleaned_data["_text_files"] = text_files
        cleaned_data["_photo_files"] = photo_files
        cleaned_data["_total_pages"] = total_printable_pages
        cleaned_data["_total_photos"] = total_photos
        cleaned_data["_total_price"] = total_price
        cleaned_data["_deleted_attachment_ids"] = list(deleted_id_set)
        return cleaned_data

    def save(self, commit=True):
        if not commit:
            return super().save(commit=False)

        total_price = self.cleaned_data.get("_total_price", Decimal("0.00"))
        country = self.cleaned_data["country"]
        text_files = self.cleaned_data.get("_text_files", [])
        photo_files = self.cleaned_data.get("_photo_files", [])
        deleted_attachment_ids = self.cleaned_data.get(
            "_deleted_attachment_ids", []
        )
        total_printable_pages = self.cleaned_data.get(
            "total_printable_pages", 0
        )
        original_status = None
        if self.instance and self.instance.pk:
            original_status = PhysicalLetter.objects.filter(
                pk=self.instance.pk,
                user=self.user,
            ).values_list("status", flat=True).first()

        with transaction.atomic():
            physical_letter = super().save(commit=False)

            if (
                self.save_as_draft
                and self.instance
                and self.instance.pk
                and original_status == PhysicalLetter.STATUS_PAID
            ):
                old_total_price = self.instance.total_price or Decimal("0.00")
                adjustment_amount = total_price - old_total_price

                user_model = get_user_model()
                locked_user = user_model.objects.select_for_update().get(
                    pk=self.user.pk
                )

                if adjustment_amount > 0 and locked_user.balance < adjustment_amount:
                    raise forms.ValidationError(
                        "Insufficient balance for this update. "
                        f"Need ${adjustment_amount:.2f}, "
                        f"available ${locked_user.balance:.2f}."
                    )

                physical_letter.user = locked_user
                physical_letter.total_pages = self.cleaned_data["_total_pages"]
                physical_letter.total_printable_pages = total_printable_pages
                physical_letter.total_photos = self.cleaned_data["_total_photos"]
                physical_letter.total_price = total_price
                physical_letter.status = PhysicalLetter.STATUS_PAID
                physical_letter.save()

                if deleted_attachment_ids and physical_letter.pk:
                    attachments_to_delete = physical_letter.attachments.filter(
                        id__in=deleted_attachment_ids
                    )
                    for attachment in attachments_to_delete:
                        attachment.file.delete(save=False)
                        attachment.delete()

                for uploaded_file in text_files:
                    self._save_attachment(
                        physical_letter,
                        uploaded_file,
                        LetterAttachment.TYPE_TEXT,
                    )
                for uploaded_file in photo_files:
                    self._save_attachment(
                        physical_letter,
                        uploaded_file,
                        LetterAttachment.TYPE_PHOTO,
                    )

                if adjustment_amount != 0:
                    transaction_type = (
                        BalanceTransaction.TYPE_DEBIT
                        if adjustment_amount > 0
                        else BalanceTransaction.TYPE_CREDIT
                    )
                    transaction_amount = (
                        -adjustment_amount
                        if adjustment_amount > 0
                        else -adjustment_amount
                    )
                    if adjustment_amount > 0:
                        locked_user.balance -= adjustment_amount
                    else:
                        locked_user.balance += (-adjustment_amount)
                    locked_user.save(update_fields=["balance"])

                    BalanceTransaction.objects.create(
                        user=locked_user,
                        amount=transaction_amount,
                        transaction_type=transaction_type,
                        reason=(
                            "Physical letter update adjustment "
                            f"#{physical_letter.id}"
                        ),
                    )

                self.user.balance = locked_user.balance
                self.adjustment_amount = adjustment_amount
                return physical_letter

            if self.save_as_draft and original_status != PhysicalLetter.STATUS_PAID:
                physical_letter.user = self.user
                physical_letter.total_pages = self.cleaned_data.get(
                    "_total_pages", total_printable_pages
                )
                physical_letter.total_printable_pages = total_printable_pages
                physical_letter.total_photos = self.cleaned_data.get(
                    "_total_photos", len(photo_files)
                )
                physical_letter.total_price = total_price
                physical_letter.status = PhysicalLetter.STATUS_DRAFT
                physical_letter.save()

                if deleted_attachment_ids and physical_letter.pk:
                    attachments_to_delete = physical_letter.attachments.filter(
                        id__in=deleted_attachment_ids
                    )
                    for attachment in attachments_to_delete:
                        attachment.file.delete(save=False)
                        attachment.delete()

                for uploaded_file in text_files:
                    self._save_attachment(
                        physical_letter,
                        uploaded_file,
                        LetterAttachment.TYPE_TEXT,
                    )
                for uploaded_file in photo_files:
                    self._save_attachment(
                        physical_letter,
                        uploaded_file,
                        LetterAttachment.TYPE_PHOTO,
                    )
                logger.info(
                    "PhysicalLetter draft saved with attachments: text=%s photo=%s id=%s",
                    len(text_files),
                    len(photo_files),
                    physical_letter.id,
                )
                return physical_letter

            user_model = get_user_model()
            updated = user_model.objects.filter(
                pk=self.user.pk,
                balance__gte=total_price,
            ).update(balance=F("balance") - total_price)
            if updated == 0:
                locked_user = user_model.objects.select_for_update().get(pk=self.user.pk)
                raise forms.ValidationError(
                    "Insufficient balance. Required: "
                    f"${total_price:.2f}. Available: ${locked_user.balance:.2f}."
                )

            locked_user = user_model.objects.get(pk=self.user.pk)
            self.user.balance = locked_user.balance

            physical_letter.user = locked_user
            physical_letter.total_pages = self.cleaned_data["_total_pages"]
            physical_letter.total_printable_pages = total_printable_pages
            physical_letter.total_photos = self.cleaned_data["_total_photos"]
            physical_letter.total_price = total_price
            physical_letter.status = PhysicalLetter.STATUS_PAID
            physical_letter.save()

            if deleted_attachment_ids and physical_letter.pk:
                attachments_to_delete = physical_letter.attachments.filter(
                    id__in=deleted_attachment_ids
                )
                for attachment in attachments_to_delete:
                    attachment.file.delete(save=False)
                    attachment.delete()

            for uploaded_file in text_files:
                self._save_attachment(
                    physical_letter,
                    uploaded_file,
                    LetterAttachment.TYPE_TEXT,
                )
            for uploaded_file in photo_files:
                self._save_attachment(
                    physical_letter,
                    uploaded_file,
                    LetterAttachment.TYPE_PHOTO,
                )
            logger.info(
                "PhysicalLetter paid saved with attachments: text=%s photo=%s id=%s",
                len(text_files),
                len(photo_files),
                physical_letter.id,
            )

            BalanceTransaction.objects.create(
                user=locked_user,
                amount=-total_price,
                transaction_type=BalanceTransaction.TYPE_DEBIT,
                reason=(
                    "Physical Letter to "
                    f"{country.country_code}"
                ),
            )

        return physical_letter


class ContactTicketForm(forms.ModelForm):
    class Meta:
        model = ContactTicket
        fields = ["email", "subject", "message"]
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "you@example.com",
                    "autocomplete": "email",
                }
            ),
            "subject": forms.TextInput(
                attrs={
                    "placeholder": "What do you need help with?",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "placeholder": "Describe your issue or question.",
                    "rows": 5,
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        base_input_classes = (
            "w-full border-0 border-b-2 border-gray-300 bg-transparent px-0 "
            "py-2 focus:border-[#014421] focus:ring-0 focus:outline-none"
        )
        self.fields["subject"].widget.attrs.update({"class": base_input_classes})
        self.fields["message"].widget.attrs.update(
            {
                "class": (
                    "w-full border border-gray-300 rounded-lg bg-transparent px-3 "
                    "py-2 text-sm focus:border-[#014421] focus:ring-0 "
                    "focus:outline-none resize-none"
                )
            }
        )

        if self.user and self.user.is_authenticated:
            self.fields["email"].required = False
            self.fields["email"].widget = forms.HiddenInput()
        else:
            self.fields["email"].required = True
            self.fields["email"].widget.attrs.update({"class": base_input_classes})

    def clean_email(self):
        if self.user and self.user.is_authenticated:
            return self.user.email.strip().lower()
        email = self.cleaned_data["email"].strip().lower()
        return email


class ContactTicketCommentForm(forms.ModelForm):
    class Meta:
        model = ContactTicketComment
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Add a comment...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message"].widget.attrs.update(
            {
                "class": (
                    "w-full border border-gray-300 rounded-lg bg-transparent px-3 "
                    "py-2 text-sm focus:border-[#014421] focus:ring-0 "
                    "focus:outline-none resize-none"
                )
            }
        )
