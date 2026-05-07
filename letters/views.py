from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.forms import (
    BalanceTopUpForm,
    DashboardPasswordChangeForm,
    SecondaryEmailForm,
    UserProfileForm,
)
from accounts.models import BalanceTransaction, SecondaryEmail
from accounts.services import send_letter_created_email
from accounts.tasks import send_pending_email_confirmation_task
from django.utils import timezone

from .billing import (
    MIN_LONG_SCHEDULE_BALANCE_USD,
    RATE_PER_YEAR_USD,
)
from decimal import Decimal
from .forms import (
    ContactTicketCommentForm,
    ContactTicketForm,
    LetterForm,
    LetterMessageEditForm,
)
from .models import ContactTicket, Letter


def landing_page(request):
    return render(request, "letters/landing.html")


def how_page(request):
    return render(request, "letters/how.html")


def _get_visible_letters_for_request(request):
    return Letter.objects.filter(user=request.user).order_by("-created_at")


def _can_access_letter(request, letter):

    return letter.user_id == request.user.id


def letters_page(request):
    guest_mode = not request.user.is_authenticated
    letters = []
    email_verification_required = False

    if not guest_mode:
        email_verification_required = not request.user.email_verified
        letters = list(_get_visible_letters_for_request(request))
        for letter in letters:
            if letter.can_view_content:
                plain_message = letter.get_message()
                letter.display_message = plain_message
                letter.display_excerpt = plain_message[:120]
                if len(plain_message) > 120:
                    letter.display_excerpt = f"{letter.display_excerpt}..."
            else:
                letter.display_message = ""
                letter.display_excerpt = "**********"

    context = {
        "letters": letters,
        "guest_mode": guest_mode,
        "email_verification_required": email_verification_required,
        "min_long_schedule_balance": MIN_LONG_SCHEDULE_BALANCE_USD,
    }
    return render(request, "letters/vault.html", context)


@login_required
def create_letter_page(request):
    if not request.user.email_verified:
        context = {
            "email_verification_required": True,
        }
        return render(request, "letters/letter_create_blocked.html", context)

    form = LetterForm(
        request.POST or None,
        user=request.user,
    )

    if request.method == "POST" and form.is_valid():
        try:
            letter = form.save()
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            schedule_cost = form.cleaned_data.get("_schedule_cost", Decimal("0.00"))
            send_letter_created_email(request, request.user, letter)

            if request.headers.get("HX-Request") == "true":
                return render(
                    request,
                    "letters/partials/letter_saved_modal.html",
                    {
                        "letter_subject": letter.subject,
                        "schedule_cost": schedule_cost if schedule_cost else None,
                        "new_balance": request.user.balance,
                    },
                )

            messages.success(request, "Letter created and added to your list.")
            return redirect("letters-page")

    user_balance = request.user.balance
    low_balance_for_long_schedule = (
        user_balance < MIN_LONG_SCHEDULE_BALANCE_USD
    )
    context = {
        "form": form,
        "user_balance": user_balance,
        "long_schedule_rate": RATE_PER_YEAR_USD,
        "min_long_schedule_balance": MIN_LONG_SCHEDULE_BALANCE_USD,
        "low_balance_for_long_schedule": low_balance_for_long_schedule,
    }
    return render(request, "letters/letter_create.html", context)


@login_required
def balance_page(request):
    form = BalanceTopUpForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        amount = form.cleaned_data["amount"]
        with transaction.atomic():
            locked_user = get_user_model().objects.select_for_update().get(
                pk=request.user.pk
            )
            locked_user.balance += amount
            locked_user.save(update_fields=["balance"])
            request.user.balance = locked_user.balance
            BalanceTransaction.objects.create(
                user=locked_user,
                amount=amount,
                reason="Manual balance top-up",
            )

        messages.success(request, f"${amount:.2f} added to your balance.")
        return redirect("balance-page")

    transactions = BalanceTransaction.objects.filter(user=request.user)
    context = {
        "balance_form": form,
        "transactions": transactions,
    }
    return render(request, "letters/balance.html", context)


@require_POST
@login_required
def delete_letter_view(request, letter_id):
    letter = get_object_or_404(Letter, id=letter_id)
    if not _can_access_letter(request, letter):
        messages.error(request, "You do not have permission to delete this letter.")
        return redirect("letters-page")

    if letter.can_be_deleted_now():
        letter.is_deleted = True
        letter.save(update_fields=["is_deleted"])
        messages.success(request, "Letter deleted.")
    elif letter.can_delete_early:
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


@require_POST
@login_required
def edit_letter_view(request, letter_id):
    letter = get_object_or_404(Letter, id=letter_id)
    if not _can_access_letter(request, letter):
        messages.error(request, "You do not have permission to edit this letter.")
        return redirect("letters-page")

    if not letter.can_be_edited_now():
        if letter.can_edit_early:
            messages.error(request, "Edit window has expired for this letter.")
        else:
            messages.error(request, "Edit is disabled for this letter.")
        return redirect("letters-page")

    form = LetterMessageEditForm(request.POST)
    if form.is_valid():
        letter.set_message(form.cleaned_data["message"])
        letter.save(update_fields=["message"])

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            message = ""
            excerpt = "**********"
            if letter.can_view_content:
                message = letter.get_message()
                excerpt = message[:120]
                if len(message) > 120:
                    excerpt = f"{excerpt}..."
            return JsonResponse(
                {
                    "ok": True,
                    "message": message,
                    "excerpt": excerpt,
                }
            )

        messages.success(request, "Letter text updated.")
    else:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Unable to update letter text.",
                },
                status=400,
            )
        messages.error(request, "Unable to update letter text.")

    return redirect("letters-page")


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
