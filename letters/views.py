import hashlib
import hmac
import json
import logging
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models import F
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST
from django.views.generic.edit import FormView

from accounts.forms import (
    BalanceTopUpForm,
    DashboardPasswordChangeForm,
    SecondaryEmailForm,
    UserProfileForm,
)
from accounts.models import BalanceTransaction, SecondaryEmail
from accounts.services import (
    send_letter_created_email,
    send_physical_letter_created_email,
)
from accounts.tasks import send_pending_email_confirmation_task
from django.utils import timezone

from .billing import (
    MIN_LONG_SCHEDULE_BALANCE_USD,
    RATE_PER_YEAR_USD,
)
from .forms import (
    ContactTicketCommentForm,
    ContactTicketForm,
    LetterForm,
    PhysicalLetterCreateForm,
)
from .models import (
    ContactTicket,
    CountryPricing,
    Letter,
    LetterAttachment,
    PhysicalLetter,
)

logger = logging.getLogger(__name__)


def landing_page(request):
    context = {}
    if request.user.is_authenticated:
        email_letters_count = Letter.objects.filter(
            user=request.user,
            is_deleted=False,
        ).count()
        physical_letters_count = PhysicalLetter.objects.filter(
            user=request.user,
        ).count()
        email_completed_count = Letter.objects.filter(
            user=request.user,
            is_delivered=True,
            is_deleted=False,
        ).count()
        physical_completed_count = PhysicalLetter.objects.filter(
            user=request.user,
            status=PhysicalLetter.STATUS_DELIVERED,
        ).count()
        context.update({
            "total_letters_count": (
                email_letters_count + physical_letters_count
            ),
            "email_letters_count": email_letters_count,
            "physical_letters_count": physical_letters_count,
            "completed_letters_count": (
                email_completed_count + physical_completed_count
            ),
        })
    # Add countries pricing for calculator
    countries_data = {}
    for item in CountryPricing.objects.all():
        countries_data[str(item.id)] = {
            "code": item.country_code,
            "name": item.country_name,
            "price": str(item.price),
        }
    context["countries_pricing_json"] = countries_data
    return render(request, "letters/landing.html", context)


def calculator_countries_fragment(request):
    """Returns <option> tags for calculator country select (HTMX target)."""
    items = CountryPricing.objects.all().order_by('country_name')
    options_html = ''.join(
        '<option value="{id}">{name} (${price})</option>'.format(
            id=item.id,
            name=item.country_name,
            price='{:.2f}'.format(float(item.price)),
        )
        for item in items
    )
    from django.http import HttpResponse
    return HttpResponse(options_html, content_type='text/html')


def how_page(request):
    # Add countries pricing for calculator
    countries_data = {}
    for item in CountryPricing.objects.all():
        countries_data[str(item.id)] = {
            "code": item.country_code,
            "name": item.country_name,
            "price": str(item.price),
        }
    context = {"countries_pricing_json": countries_data}
    return render(request, "letters/how.html", context)


def faq_page(request):
    return render(request, "letters/faq.html")


def terms_page(request):
    return render(request, "letters/terms.html")


def _get_visible_letters_for_request(request):
    return Letter.objects.filter(user=request.user).order_by("-created_at")


def _can_access_letter(request, letter):

    return letter.user_id == request.user.id


def _can_access_physical_letter(request, letter):
    return letter.user_id == request.user.id


def _calculate_physical_letter_years_passed(letter):
    """Calculate how many full years have passed since letter creation."""
    days_passed = (timezone.now() - letter.created_at).days
    years_passed = max(0, days_passed // 365)
    return years_passed


def _calculate_physical_letter_deletion_info(letter):
    """
    Calculate deletion fee and refund for a physical letter.
    Fee = 1 USD + (years_passed * 0.5 USD)
    Refund = total_price - fee
    """
    years_passed = _calculate_physical_letter_years_passed(letter)
    fee = Decimal("1.00") + (Decimal(str(years_passed)) * Decimal("0.50"))
    refund = letter.total_price - fee
    return {
        "years_passed": years_passed,
        "fee": fee,
        "refund": max(Decimal("0.00"), refund),
    }


def _calculate_email_letter_deletion_info(letter):
    """
    Calculate deletion fee and refund for an email letter.

    Non-free letters keep a fixed $0.50 fee and refund the remainder.
    Free letters have no fee and no refund.
    """
    total_price = letter.total_price or Decimal("0.00")
    if total_price > 0:
        fee = Decimal("0.50")
    else:
        fee = Decimal("0.00")
    refund = total_price - fee
    return {
        "fee": fee,
        "refund": max(Decimal("0.00"), refund),
        "total_price": total_price,
    }


def letters_page(request):
    guest_mode = not request.user.is_authenticated
    letters = []
    sort_by = (request.GET.get("sort") or "newest").strip().lower()
    valid_sorts = {"newest", "oldest", "price_low", "price_high"}
    if sort_by not in valid_sorts:
        sort_by = "newest"
    email_verification_required = False

    if not guest_mode:
        email_verification_required = not request.user.email_verified
        email_letters = list(_get_visible_letters_for_request(request))
        physical_letters = list(
            PhysicalLetter.objects.filter(user=request.user)
            .select_related("country")
            .order_by("-created_at")
        )
        print(physical_letters)
        for letter in email_letters:
            if letter.can_view_content:
                plain_message = letter.get_message()
                letter.display_message = plain_message
                letter.display_excerpt = plain_message[:120]
                if len(plain_message) > 120:
                    letter.display_excerpt = f"{letter.display_excerpt}..."
            else:
                letter.display_message = ""
                letter.display_excerpt = "**********"

        letters = []
        for letter in email_letters:
            letters.append(
                {
                    "type": "email",
                    "id": letter.id,
                    "title": letter.subject,
                    "status": letter.status_label,
                    "status_value": "",
                    "created_at": letter.created_at,
                    "price": letter.total_price,
                    "destination": (
                        "Only me"
                        if letter.send_to_me
                        else letter.recipient_email
                    ),
                    "detail_url": reverse(
                        "letter-detail",
                        kwargs={"kind": "email", "item_id": letter.id},
                    ),
                    "raw": letter,
                }
            )
        for letter in physical_letters:
            detail_url = reverse(
                "letter-detail",
                kwargs={"kind": "physical", "item_id": letter.id},
            )
            if letter.status == PhysicalLetter.STATUS_DRAFT:
                detail_url = f"{reverse('physical-letter-create')}?draft={letter.id}"

            letters.append(
                {
                    "type": "physical",
                    "id": letter.id,
                    "title": (
                        f"Draft physical letter #{letter.id}"
                        if letter.status == PhysicalLetter.STATUS_DRAFT
                        else f"Physical letter to {letter.recipient_name}"
                    ),
                    "status": letter.get_status_display(),
                    "status_value": letter.status,
                    "created_at": letter.created_at,
                    "price": letter.total_price,
                    "destination": (
                        f"{letter.country.country_name} ({letter.country.country_code})"
                    ),
                    "detail_url": detail_url,
                    "raw": letter,
                }
            )

        if sort_by == "newest":
            letters.sort(key=lambda x: x["created_at"], reverse=True)
        elif sort_by == "oldest":
            letters.sort(key=lambda x: x["created_at"])
        elif sort_by == "price_low":
            letters.sort(
                key=lambda x: (
                    x["price"],
                    -x["created_at"].timestamp(),
                )
            )
        elif sort_by == "price_high":
            letters.sort(
                key=lambda x: (
                    -x["price"],
                    -x["created_at"].timestamp(),
                )
            )

    context = {
        "letters": letters,
        "sort_by": sort_by,
        "guest_mode": guest_mode,
        "email_verification_required": email_verification_required,
        "min_long_schedule_balance": MIN_LONG_SCHEDULE_BALANCE_USD,
    }
    # Add countries pricing for calculator
    countries_data = {}
    for item in CountryPricing.objects.all():
        countries_data[str(item.id)] = {
            "code": item.country_code,
            "name": item.country_name,
            "price": str(item.price),
        }
    context["countries_pricing_json"] = countries_data
    return render(request, "letters/vault.html", context)


@login_required
def create_letter_page(request):
    if not request.user.email_verified:
        context = {
            "email_verification_required": True,
        }
        return render(request, "letters/letter_create_blocked.html", context)

    current_letter = None
    draft_id = request.GET.get("draft") or request.POST.get("draft")
    if draft_id:
        try:
            current_letter = Letter.objects.get(
                id=int(draft_id),
                user=request.user,
            )
        except (ValueError, Letter.DoesNotExist):
            messages.error(request, "Email letter not found.")
            return redirect("letters-page")

        if not current_letter.can_be_edited_now():
            messages.error(request, "This email letter can no longer be edited.")
            return redirect(
                reverse(
                    "letter-detail",
                    kwargs={"kind": "email", "item_id": current_letter.id},
                )
            )

    form = LetterForm(
        request.POST or None,
        user=request.user,
        instance=current_letter,
    )

    if request.method == "POST" and form.is_valid():
        try:
            letter = form.save()
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            schedule_cost = form.cleaned_data.get("_schedule_cost", Decimal("0.00"))
            adjustment_amount = form.cleaned_data.get(
                "_adjustment_amount",
                schedule_cost,
            )
            if current_letter is None:
                send_letter_created_email(request, request.user, letter)

            if request.headers.get("HX-Request") == "true":
                if current_letter is not None:
                    adjustment_text = "No pricing changes were needed."
                    if adjustment_amount > 0:
                        adjustment_text = (
                            f"Additional charge: ${adjustment_amount:.2f} "
                            "deducted from your balance."
                        )
                    elif adjustment_amount < 0:
                        refund_amount = -adjustment_amount
                        adjustment_text = (
                            f"Refund: ${refund_amount:.2f} credited "
                            "to your balance."
                        )

                    return render(
                        request,
                        "letters/partials/operation_success.html",
                        {
                            "operation_type": "Email Letter",
                            "title": "Letter Updated",
                            "message": (
                                "Your email letter was updated successfully. "
                                f"{adjustment_text}"
                            ),
                            "show_create_button": True,
                        },
                    )

                return render(
                    request,
                    "letters/partials/letter_saved_modal.html",
                    {
                        "letter_subject": letter.subject,
                        "schedule_cost": schedule_cost if schedule_cost else None,
                        "new_balance": request.user.balance,
                        "adjustment_amount": adjustment_amount,
                        "is_edit_mode": current_letter is not None,
                    },
                )

            if current_letter is not None:
                messages.success(request, "Email letter updated.")
            else:
                messages.success(request, "Letter created and added to your list.")
            return redirect("letters-page")

    user_balance = request.user.balance
    low_balance_for_long_schedule = (
        user_balance < MIN_LONG_SCHEDULE_BALANCE_USD
    )
    context = {
        "form": form,
        "current_letter": current_letter,
        "original_total_price": (
            current_letter.total_price
            if current_letter is not None
            else Decimal("0.00")
        ),
        "user_balance": user_balance,
        "long_schedule_rate": RATE_PER_YEAR_USD,
        "min_long_schedule_balance": MIN_LONG_SCHEDULE_BALANCE_USD,
        "low_balance_for_long_schedule": low_balance_for_long_schedule,
    }
    return render(request, "letters/letter_create.html", context)


class PhysicalLetterCreateView(FormView):
    template_name = "letters/physical_letter_create.html"
    form_class = PhysicalLetterCreateForm
    success_url = reverse_lazy("letters-page")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        self.current_draft = self._get_current_draft()
        return super().dispatch(request, *args, **kwargs)

    def _is_draft_action(self):
        return self.request.method == "POST" and (
            self.request.POST.get("action") == "draft"
        )

    def _get_current_draft(self):
        draft_id = (
            self.request.GET.get("draft")
            or self.request.POST.get("draft")
        )
        if not draft_id:
            return None
        try:
            letter = PhysicalLetter.objects.get(
                id=int(draft_id),
                user=self.request.user,
            )
            if letter.status in (
                PhysicalLetter.STATUS_DRAFT,
                PhysicalLetter.STATUS_PAID,
            ):
                return letter
            return None
        except (ValueError, PhysicalLetter.DoesNotExist):
            return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["files"] = self.request.FILES or None
        kwargs["save_as_draft"] = self._is_draft_action()
        if self.current_draft is not None:
            kwargs["instance"] = self.current_draft
        return kwargs

    def _countries_payload(self):
        data = {}
        for item in CountryPricing.objects.all():
            data[str(item.id)] = {
                "code": item.country_code,
                "name": item.country_name,
                "price": str(item.price),
            }
        return data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        existing_text_files_count = 0
        existing_photo_files_count = 0
        existing_attachments = []
        active_letter = self.current_draft
        bound_form = context.get("form")
        if (
            active_letter is None
            and bound_form is not None
            and getattr(bound_form, "instance", None)
            and getattr(bound_form.instance, "pk", None)
        ):
            active_letter = bound_form.instance

        if active_letter is not None:
            existing_text_files_count = active_letter.attachments.filter(
                attachment_type=LetterAttachment.TYPE_TEXT,
            ).count()
            existing_photo_files_count = active_letter.attachments.filter(
                attachment_type=LetterAttachment.TYPE_PHOTO,
            ).count()
            existing_attachments = list(
                active_letter.attachments.order_by("created_at")
            )

        context["user_balance"] = self.request.user.balance
        context["current_draft"] = self.current_draft
        context["original_total_price"] = (
            self.current_draft.total_price
            if self.current_draft is not None
            else Decimal("0.00")
        )
        context["drafts"] = PhysicalLetter.objects.filter(
            user=self.request.user,
            status=PhysicalLetter.STATUS_DRAFT,
        ).order_by("-updated_at")
        context["existing_text_files_count"] = existing_text_files_count
        context["existing_photo_files_count"] = existing_photo_files_count
        context["existing_attachments"] = existing_attachments
        context["countries_pricing_json"] = self._countries_payload()
        context["max_text_files"] = settings.PHYSICAL_LETTER_MAX_TEXT_FILES
        context["max_photo_files"] = settings.PHYSICAL_LETTER_MAX_PHOTO_FILES
        context["max_file_size_mb"] = settings.PHYSICAL_LETTER_MAX_FILE_SIZE_MB
        context["max_delivery_years"] = settings.PHYSICAL_LETTER_MAX_DELIVERY_YEARS
        context["extra_photo_price"] = (
            settings.PHYSICAL_LETTER_EXTRA_PHOTO_PRICE_USD
        )
        context["extra_page_price"] = (
            settings.PHYSICAL_LETTER_EXTRA_PAGE_PRICE_USD
        )
        context["extra_year_price"] = (
            settings.PHYSICAL_LETTER_EXTRA_YEAR_PRICE_USD
        )
        context["text_chars_per_page"] = (
            settings.PHYSICAL_LETTER_TEXT_CHARS_PER_PAGE
        )
        return context

    def form_valid(self, form):
        logger.info(
            "PhysicalLetter form_valid entered: action=%s keys=%s",
            self.request.POST.get("action"),
            list(self.request.FILES.keys()),
        )
        form.save_as_draft = self._is_draft_action()
        try:
            letter = form.save()
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
            return self.form_invalid(form)

        if self._is_draft_action():
            message = "Your draft has been saved. You can edit and pay later."
            if (
                self.current_draft
                and self.current_draft.status == PhysicalLetter.STATUS_PAID
            ):
                adjustment = getattr(form, "adjustment_amount", Decimal("0.00"))
                adjustment_text = "No pricing changes were needed."
                if adjustment > 0:
                    adjustment_text = (
                        f"Additional charge: ${adjustment:.2f} deducted "
                        "from your balance."
                    )
                elif adjustment < 0:
                    refund = -adjustment
                    adjustment_text = (
                        f"Refund: ${refund:.2f} credited to your balance."
                    )
                message = (
                    f"Your physical letter was updated successfully. "
                    f"{adjustment_text}"
                )
                title = "Letter Updated"
            else:
                title = "Draft Saved"

            if self.request.headers.get("HX-Request") == "true":
                is_draft = (
                    self.current_draft is None
                    or self.current_draft.status == PhysicalLetter.STATUS_DRAFT
                )
                is_paid = (
                    self.current_draft
                    and self.current_draft.status == PhysicalLetter.STATUS_PAID
                )
                return render(
                    self.request,
                    "letters/partials/operation_success.html",
                    {
                        "operation_type": "Physical Letter",
                        "title": title,
                        "message": message,
                        "draft_info": is_draft,
                        "draft_id": letter.id if is_draft else None,
                        "show_continue_button": is_draft,
                        "show_create_button": is_paid,
                    },
                )

            messages.success(self.request, message)
            return redirect("letters-page")

        # Send confirmation email for new paid physical letters
        if self.current_draft is None:
            try:
                send_physical_letter_created_email(
                    self.request,
                    self.request.user,
                    letter,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to send physical letter confirmation email: %s",
                    str(exc),
                )

        if self.request.headers.get("HX-Request") == "true":
            return render(
                self.request,
                "letters/partials/operation_success.html",
                {
                    "operation_type": "Physical Letter",
                    "title": "Letter Created",
                    "message": (
                        "Your physical letter has been created. "
                        "Files are ready for admin printing."
                    ),
                    "show_create_button": True,
                },
            )

        messages.success(
            self.request,
            "Physical letter created. Files are ready for admin printing.",
        )
        messages.info(
            self.request,
            (
                "Delivery depends on destination country and can occur "
                "1-4 days after your requested date."
            ),
        )

        self.current_draft = None
        self.current_paid_letter = None
        return render(
            self.request,
            self.template_name,
            self.get_context_data(
                form=self.form_class(user=self.request.user),
                created_letter=letter,
            ),
        )

    def form_invalid(self, form):
        logger.warning(
            "PhysicalLetter form_invalid: errors=%s non_field=%s",
            form.errors.as_json(),
            form.non_field_errors(),
        )
        return super().form_invalid(form)


@login_required
def balance_page(request):
    form = BalanceTopUpForm()

    transactions = BalanceTransaction.objects.filter(user=request.user)
    context = {
        "balance_form": form,
        "transactions": transactions,
    }
    return render(request, "letters/balance.html", context)


def _build_lemonsqueezy_checkout_payload(
    *,
    request,
    amount_cents,
):
    success_url = request.build_absolute_uri(reverse("payment-success"))
    error_url = request.build_absolute_uri(reverse("payment-error"))
    return {
        "data": {
            "type": "checkouts",
            "attributes": {
                "custom_price": amount_cents,
                "product_options": {
                    "redirect_url": success_url,
                    "receipt_button_text": "Back to LetterGator",
                    "receipt_link_url": success_url,
                },
                "checkout_data": {
                    "custom": {
                        "user_id": str(request.user.id),
                        "top_up_amount_cents": str(amount_cents),
                        "success_url": success_url,
                        "error_url": error_url,
                    },
                },
            },
            "relationships": {
                "store": {
                    "data": {
                        "type": "stores",
                        "id": settings.LEMONSQUEEZY_STORE_ID,
                    }
                },
                "variant": {
                    "data": {
                        "type": "variants",
                        "id": settings.LEMONSQUEEZY_VARIANT_ID,
                    }
                },
            },
        }
    }


@login_required
@require_POST
def create_checkout_view(request):
    form = BalanceTopUpForm(request.POST or None)
    if not form.is_valid():
        transactions = BalanceTransaction.objects.filter(user=request.user)
        return render(
            request,
            "letters/balance.html",
            {
                "balance_form": form,
                "transactions": transactions,
            },
            status=400,
        )

    if not settings.LEMONSQUEEZY_API_KEY:
        messages.error(request, "Payment provider is not configured yet.")
        return redirect("balance-page")

    if not settings.LEMONSQUEEZY_STORE_ID or not settings.LEMONSQUEEZY_VARIANT_ID:
        messages.error(
            request,
            "Payment provider IDs are missing. Please contact support.",
        )
        return redirect("balance-page")

    amount = form.cleaned_data["amount"]
    amount_cents = int((amount * 100).quantize(Decimal("1")))
    payload = _build_lemonsqueezy_checkout_payload(
        request=request,
        amount_cents=amount_cents,
    )
    headers = {
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
        "Authorization": f"Bearer {settings.LEMONSQUEEZY_API_KEY}",
    }

    try:
        response = requests.post(
            f"{settings.LEMONSQUEEZY_API_BASE}/v1/checkouts",
            json=payload,
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Failed to create Lemon Squeezy checkout: %s", exc)
        messages.error(
            request,
            "Could not start checkout right now. Please try again.",
        )
        return redirect("balance-page")

    checkout_url = (
        response.json().get("data", {}).get("attributes", {}).get("url")
    )
    if not checkout_url:
        messages.error(
            request,
            "Checkout URL was not returned by payment provider.",
        )
        return redirect("balance-page")

    return redirect(checkout_url)


@login_required
def payment_success_view(request):
    return render(request, "letters/payment_success.html")


@login_required
def payment_error_view(request):
    return render(request, "letters/payment_error.html")


def _extract_user_id_from_payload(payload):
    custom_data = payload.get("meta", {}).get("custom_data", {})
    if not custom_data:
        custom_data = payload.get("data", {}).get("attributes", {}).get(
            "custom_data",
            {},
        )
    user_id = custom_data.get("user_id")
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


def _extract_order_id(payload):
    order_id = payload.get("data", {}).get("id")
    if order_id is None:
        return None
    return str(order_id)


def _extract_total_amount(payload):
    custom_data = payload.get("meta", {}).get("custom_data", {})
    if not custom_data:
        custom_data = payload.get("data", {}).get("attributes", {}).get(
            "custom_data",
            {},
        )

    amount_in_cents = custom_data.get("top_up_amount_cents")
    if amount_in_cents is None:
        amount_in_cents = payload.get("data", {}).get("attributes", {}).get(
            "total"
        )
    if amount_in_cents is None:
        return None

    try:
        amount = Decimal(str(amount_in_cents)) / Decimal("100")
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


@csrf_exempt
@require_POST
def lemonsqueezy_webhook_view(request):
    provided_signature = request.headers.get("X-Signature", "")
    webhook_secret = settings.LEMONSQUEEZY_WEBHOOK_SECRET
    if not webhook_secret:
        logger.error("LEMONSQUEEZY_WEBHOOK_SECRET is not configured")
        return HttpResponse(status=500)

    digest = hmac.new(
        webhook_secret.encode("utf-8"),
        request.body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(digest, provided_signature):
        return HttpResponse(status=401)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(status=400)

    event_name = payload.get("meta", {}).get("event_name")
    if event_name != "order_created":
        return HttpResponse(status=200)

    user_id = _extract_user_id_from_payload(payload)
    order_id = _extract_order_id(payload)
    amount = _extract_total_amount(payload)
    if user_id is None or order_id is None or amount is None:
        return HttpResponse(status=400)

    user_model = get_user_model()
    try:
        with transaction.atomic():
            if BalanceTransaction.objects.filter(external_id=order_id).exists():
                return HttpResponse(status=200)

            updated = user_model.objects.filter(pk=user_id).update(
                balance=F("balance") + amount
            )
            if updated == 0:
                return HttpResponse(status=404)

            BalanceTransaction.objects.create(
                user_id=user_id,
                amount=amount,
                transaction_type=BalanceTransaction.TYPE_CREDIT,
                external_id=order_id,
                reason="Lemon Squeezy top-up",
            )
    except IntegrityError:
        return HttpResponse(status=200)

    return HttpResponse(status=200)


@require_http_methods(['POST', 'DELETE'])
@login_required
def delete_letter_view(request, letter_id):
    letter = get_object_or_404(Letter, id=letter_id)
    if not _can_access_letter(request, letter):
        messages.error(request, "You do not have permission to delete this letter.")
        return redirect("letters-page")

    if not letter.can_be_deleted_now():
        if letter.can_delete_early:
            messages.error(
                request,
                "Delete window has expired for this letter.",
            )
        else:
            messages.error(
                request,
                "Delete is disabled for this letter.",
            )
        return redirect("letters-page")

    deletion_info = _calculate_email_letter_deletion_info(letter)
    refund_amount = deletion_info["refund"]
    fee_amount = deletion_info["fee"]

    with transaction.atomic():
        if refund_amount > 0:
            user_model = get_user_model()
            locked_user = user_model.objects.select_for_update().get(
                pk=letter.user.pk,
            )
            locked_user.balance += refund_amount
            locked_user.save(update_fields=["balance"])
            BalanceTransaction.objects.create(
                user=locked_user,
                amount=refund_amount,
                transaction_type=BalanceTransaction.TYPE_CREDIT,
                reason=(
                    "Refund for deleted email letter "
                    f"#{letter.id}"
                ),
            )
            request.user.balance = locked_user.balance

        letter.delete()

    if request.headers.get("HX-Request") == "true":
        if refund_amount > 0:
            message = (
                "Your email letter has been permanently deleted. "
                f"We kept ${fee_amount:.2f} and refunded "
                f"${refund_amount:.2f} to your balance."
            )
        else:
            message = "Your email letter has been permanently deleted."

        return render(
            request,
            "letters/partials/operation_success.html",
            {
                "operation_type": "Email Letter",
                "title": "Letter Deleted",
                "message": message,
                "show_create_button": True,
            },
        )

    if refund_amount > 0:
        messages.success(
            request,
            "Email letter deleted. "
            f"We kept ${fee_amount:.2f} and refunded "
            f"${refund_amount:.2f} to your account.",
        )
    else:
        messages.success(request, "Letter deleted.")
    return redirect("letters-page")


@login_required
def letter_detail_view(request, kind, item_id):
    normalized_kind = (kind or "").strip().lower()
    if normalized_kind == "email":
        letter = get_object_or_404(Letter, id=item_id)
        if not _can_access_letter(request, letter):
            raise Http404()

        if letter.can_view_content:
            message_text = letter.get_message()
        else:
            message_text = "**********"

        context = {
            "letter": letter,
            "message_text": message_text,
        }
        return render(request, "letters/letter_detail_email.html", context)

    if normalized_kind == "physical":
        letter = get_object_or_404(
            PhysicalLetter.objects.select_related("country"),
            id=item_id,
        )
        if not _can_access_physical_letter(request, letter):
            raise Http404()

        if letter.status == PhysicalLetter.STATUS_DRAFT:
            return redirect(f"{reverse('physical-letter-create')}?draft={letter.id}")

        attachments = list(letter.attachments.order_by("created_at"))
        context = {
            "letter": letter,
            "attachments": attachments,
        }
        return render(request, "letters/letter_detail_physical.html", context)

    raise Http404()


@require_http_methods(['POST', 'DELETE'])
@login_required
def delete_physical_draft_view(request, letter_id):
    letter = get_object_or_404(PhysicalLetter, id=letter_id)
    if not _can_access_physical_letter(request, letter):
        messages.error(
            request,
            "You do not have permission to delete this physical letter.",
        )
        return redirect("letters-page")

    # Only allow deletion if status is DRAFT or PAID
    if letter.status not in (PhysicalLetter.STATUS_DRAFT, PhysicalLetter.STATUS_PAID):
        messages.error(
            request,
            "This physical letter can no longer be deleted.",
        )
        return redirect("letters-page")

    # Use transaction to ensure atomicity
    with transaction.atomic():
        # Delete all attachments from S3
        for attachment in letter.attachments.all():
            attachment.file.delete(save=False)
            attachment.delete()

        # Only process refund if letter was PAID (drafts have no payment)
        if letter.status == PhysicalLetter.STATUS_PAID:
            deletion_info = _calculate_physical_letter_deletion_info(letter)
            refund_amount = deletion_info["refund"]

            # Create refund transaction if there's a refund amount
            if refund_amount > 0:
                BalanceTransaction.objects.create(
                    user=letter.user,
                    amount=refund_amount,
                    transaction_type=BalanceTransaction.TYPE_CREDIT,
                    reason=f"Refund for deleted physical letter #{letter.id}",
                )
                # Update user balance
                letter.user.balance += refund_amount
                letter.user.save(update_fields=["balance"])

            # Delete the letter
            letter.delete()

            # Check if this is an HTMX request
            if request.headers.get("HX-Request") == "true":
                refund_message = (
                    f"Refund of ${refund_amount:.2f} has been credited to your balance."
                    if refund_amount > 0
                    else ""
                )
                return render(
                    request,
                    "letters/partials/operation_success.html",
                    {
                        "operation_type": "Physical Letter",
                        "title": "Letter Deleted",
                        "message": "Your physical letter has been permanently deleted.",
                        "refund_info": refund_message,
                        "show_create_button": True,
                    },
                )

            messages.success(
                request,
                f"Physical letter deleted. Refund of ${refund_amount:.2f} has been credited to your account."
                if refund_amount > 0
                else "Physical letter deleted.",
            )
        else:
            # Draft deletion - no refund
            letter.delete()

            # Check if this is an HTMX request
            if request.headers.get("HX-Request") == "true":
                return render(
                    request,
                    "letters/partials/operation_success.html",
                    {
                        "operation_type": "Draft Letter",
                        "title": "Draft Deleted",
                        "message": "Your draft has been permanently deleted.",
                        "show_create_button": True,
                    },
                )

            messages.success(request, "Draft deleted.")

    return redirect("letters-page")


def get_deletion_info_view(request):
    """
    API endpoint to get deletion fee and refund info.
    Query params: letter_type (email|physical), letter_id
    """
    # Check authentication
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Authentication required"},
            status=401,
        )

    letter_type = request.GET.get("letter_type", "").strip().lower()
    letter_id = request.GET.get("letter_id", "").strip()

    if not letter_type or not letter_id:
        return JsonResponse(
            {"error": "Missing letter_type or letter_id"},
            status=400,
        )

    try:
        letter_id = int(letter_id)
    except (ValueError, TypeError):
        return JsonResponse(
            {"error": "Invalid letter_id"},
            status=400,
        )

    if letter_type == "email":
        letter = get_object_or_404(Letter, id=letter_id)
        if not _can_access_letter(request, letter):
            return JsonResponse(
                {"error": "Permission denied"},
                status=403,
            )

        if not letter.can_be_deleted_now():
            return JsonResponse(
                {
                    "error": "This email letter can no longer be deleted.",
                    "can_delete": False,
                },
                status=400,
            )

        deletion_info = _calculate_email_letter_deletion_info(letter)
        fee_amount = deletion_info["fee"]
        refund_amount = deletion_info["refund"]
        total_price = deletion_info["total_price"]

        if total_price > 0:
            message = (
                f"We will keep ${fee_amount:.2f} as a non-refundable "
                f"processing fee. ${refund_amount:.2f} will be refunded "
                "to your balance."
            )
        else:
            message = (
                "This email letter is free. It will be permanently deleted "
                "with no refund."
            )

        return JsonResponse({
            "letter_type": "email",
            "can_delete": True,
            "fee": f"{fee_amount:.2f}",
            "refund": f"{refund_amount:.2f}",
            "total_price": f"{total_price:.2f}",
            "message": message,
        })

    elif letter_type == "physical":
        letter = get_object_or_404(PhysicalLetter, id=letter_id)
        if not _can_access_physical_letter(request, letter):
            return JsonResponse(
                {"error": "Permission denied"},
                status=403,
            )

        # Check if deletion is allowed
        if letter.status not in (PhysicalLetter.STATUS_DRAFT, PhysicalLetter.STATUS_PAID):
            return JsonResponse(
                {
                    "error": "This physical letter can no longer be deleted.",
                    "can_delete": False,
                },
                status=400,
            )

        # Different messages for draft vs paid
        if letter.status == PhysicalLetter.STATUS_DRAFT:
            return JsonResponse({
                "letter_type": "physical",
                "status": "draft",
                "can_delete": True,
                "fee": "0.00",
                "refund": "0.00",
                "message": "This is a draft letter. No payment was made, so no refund will be issued.",
            })
        else:
            # PAID status - calculate fee and refund
            deletion_info = _calculate_physical_letter_deletion_info(letter)
            return JsonResponse({
                "letter_type": "physical",
                "status": "paid",
                "can_delete": True,
                "fee": f"{deletion_info['fee']:.2f}",
                "refund": f"{deletion_info['refund']:.2f}",
                "years_passed": deletion_info["years_passed"],
                "total_price": f"{letter.total_price:.2f}",
                "message": (
                    f"We will keep ${deletion_info['fee']:.2f} "
                    f"({int(deletion_info['years_passed'])} years × $0.50 + $1.00 base fee). "
                    f"${deletion_info['refund']:.2f} will be refunded to your balance."
                ),
            })

    else:
        return JsonResponse(
            {"error": "Invalid letter_type"},
            status=400,
        )


def concept_page(request):
    return render(request, "letters/concept.html")


def privacy_page(request):
    return render(request, "letters/privacy.html")


def _visible_contact_tickets_for_request(request):
    if not request.user.is_authenticated:
        return ContactTicket.objects.none()
    normalized_email = request.user.email.strip().lower()
    return ContactTicket.objects.filter(
        Q(user=request.user) | Q(email__iexact=normalized_email)
    ).distinct().order_by("-created_at")


def contact_page(request):
    form = ContactTicketForm(
        request.POST or None,
        user=request.user,
    )
    panel_message = ""
    panel_message_level = "success"

    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        if request.user.is_authenticated:
            ticket.user = request.user
        ticket.email = form.cleaned_data["email"]
        ticket.save()
        panel_message = "Your message was sent. We will get back to you soon."
        panel_message_level = "success"
        form = ContactTicketForm(user=request.user)

    tickets = _visible_contact_tickets_for_request(request)
    context = {
        "contact_form": form,
        "tickets": tickets,
        "panel_message": panel_message,
        "panel_message_level": panel_message_level,
        "comment_form": ContactTicketCommentForm(),
    }
    return render(request, "letters/contact.html", context)


@login_required
@require_POST
def contact_ticket_comment_view(request, ticket_id):
    ticket = get_object_or_404(
        ContactTicket,
        Q(id=ticket_id),
        Q(user=request.user) | Q(email__iexact=request.user.email.strip().lower()),
    )
    form = ContactTicketCommentForm(request.POST)
    panel_comment_form = form
    if form.is_valid():
        comment = form.save(commit=False)
        comment.ticket = ticket
        comment.author = request.user
        comment.commenter_email = request.user.email.strip().lower()
        comment.is_admin_comment = request.user.is_staff
        comment.save()
        panel_comment_form = ContactTicketCommentForm()

    context = {
        "ticket": ticket,
        "comment_form": ContactTicketCommentForm(),
        "panel_comment_form": panel_comment_form,
    }
    return render(request, "letters/partials/contact_ticket_card.html", context)


@login_required
def dashboard_password_change_view(request):
    expanded = request.GET.get("expanded") == "1"
    password_change_form = DashboardPasswordChangeForm(
        request.user,
        prefix="password",
    )

    if request.method == "POST":
        expanded = True
        password_change_form = DashboardPasswordChangeForm(
            request.user,
            request.POST,
            prefix="password",
        )
        if password_change_form.is_valid():
            user = password_change_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password updated successfully.")
            return HttpResponse(
                status=204,
                headers={"HX-Redirect": reverse("dashboard_view")},
            )

    context = {
        "password_change_form": password_change_form,
        "password_form_expanded": expanded,
    }
    return render(
        request,
        "letters/partials/password_change_panel.html",
        context,
    )


@login_required
def dashboard_secondary_emails_view(request):
    panel_message = ""
    panel_message_level = "success"
    secondary_email_form = SecondaryEmailForm(
        user=request.user,
        prefix="secondary",
    )

    if request.method == "POST":
        action = request.POST.get("action", "add_secondary_email")
        if action == "add_secondary_email":
            secondary_email_form = SecondaryEmailForm(
                request.POST,
                user=request.user,
                prefix="secondary",
            )
            if secondary_email_form.is_valid():
                secondary_email = secondary_email_form.save(commit=False)
                secondary_email.user = request.user
                secondary_email.save()
                secondary_email_form = SecondaryEmailForm(
                    user=request.user,
                    prefix="secondary",
                )
                panel_message = "Secondary email added."
                panel_message_level = "success"
        elif action == "remove_secondary_email":
            secondary_email_id = request.POST.get("secondary_email_id")
            deleted, _ = SecondaryEmail.objects.filter(
                id=secondary_email_id,
                user=request.user,
            ).delete()
            if deleted:
                panel_message = "Secondary email removed."
                panel_message_level = "success"

    secondary_emails = request.user.secondary_emails.all()
    context = {
        "secondary_email_form": secondary_email_form,
        "secondary_emails": secondary_emails,
        "secondary_slots_left": max(0, 5 - secondary_emails.count()),
        "panel_message": panel_message,
        "panel_message_level": panel_message_level,
    }
    return render(
        request,
        "letters/partials/secondary_email_panel.html",
        context,
    )


@login_required
def dashboard_view(request):
    profile_form = UserProfileForm(instance=request.user, prefix="profile")
    secondary_email_form = SecondaryEmailForm(
        user=request.user,
        prefix="secondary",
    )

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "update_profile":
            current_email = request.user.email.strip().lower()
            profile_form = UserProfileForm(
                request.POST,
                instance=request.user,
                prefix="profile",
            )
            if profile_form.is_valid():
                user = request.user
                new_full_name = profile_form.cleaned_data["full_name"]
                requested_email = profile_form.cleaned_data["email"].strip().lower()

                user.full_name = new_full_name
                user.phone_number = profile_form.cleaned_data.get("phone_number", "")
                user.address = profile_form.cleaned_data.get("address", "")

                if requested_email != current_email:
                    user.pending_email = requested_email
                    user.pending_email_requested_at = timezone.now()
                    user.save(
                        update_fields=[
                            "full_name",
                            "phone_number",
                            "address",
                            "pending_email",
                            "pending_email_requested_at",
                        ]
                    )
                    send_pending_email_confirmation_task.delay(
                        user.id,
                        request.build_absolute_uri("/"),
                    )
                    messages.success(
                        request,
                        "Confirmation link queued for your new email. "
                        "Primary email will be updated after confirmation.",
                    )
                else:
                    user.save(update_fields=["full_name", "phone_number", "address"])
                    messages.success(request, "Profile updated successfully.")
                return redirect("dashboard_view")

        elif action == "cancel_pending_email_update":
            user = request.user
            if user.pending_email:
                user.pending_email = ""
                user.pending_email_requested_at = None
                user.save(
                    update_fields=[
                        "pending_email",
                        "pending_email_requested_at",
                    ]
                )
                messages.success(
                    request,
                    "Pending email update canceled. Your current primary email was kept.",
                )
            else:
                messages.info(request, "No pending email change found.")
            return redirect("dashboard_view")

    secondary_emails = request.user.secondary_emails.all()
    context = {
        "profile_form": profile_form,
        "secondary_email_form": secondary_email_form,
        "secondary_emails": secondary_emails,
        "secondary_slots_left": max(0, 5 - secondary_emails.count()),
        "email_verification_required": not request.user.email_verified,
        "pending_primary_email": request.user.pending_email,
    }
    return render(request, "letters/dashboard.html", context)
