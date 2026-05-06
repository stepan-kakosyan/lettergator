from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.forms import SecondaryEmailForm, UserProfileForm
from accounts.models import SecondaryEmail
from accounts.services import send_letter_created_email
from accounts.tasks import send_pending_email_confirmation_task
from django.utils import timezone

from .forms import LetterForm, LetterMessageEditForm
from .models import Letter


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
        letter = form.save()
        send_letter_created_email(request, request.user, letter)

        messages.success(request, "Letter created and added to your list.")
        return redirect("letters-page")

    context = {
        "form": form,
    }
    return render(request, "letters/letter_create.html", context)


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

                if requested_email != current_email:
                    user.pending_email = requested_email
                    user.pending_email_requested_at = timezone.now()
                    user.save(
                        update_fields=[
                            "full_name",
                            "pending_email",
                            "pending_email_requested_at",
                        ]
                    )
                    send_pending_email_confirmation_task.delay(user.id)
                    messages.success(
                        request,
                        "Confirmation link queued for your new email. "
                        "Primary email will be updated after confirmation.",
                    )
                else:
                    user.save(update_fields=["full_name"])
                    messages.success(request, "Profile updated successfully.")
                return redirect("dashboard_view")

        elif action == "add_secondary_email":
            secondary_email_form = SecondaryEmailForm(
                request.POST,
                user=request.user,
                prefix="secondary",
            )
            if secondary_email_form.is_valid():
                secondary_email = secondary_email_form.save(commit=False)
                secondary_email.user = request.user
                secondary_email.save()
                messages.success(request, "Secondary email added.")
                return redirect("dashboard_view")

        elif action == "remove_secondary_email":
            secondary_email_id = request.POST.get("secondary_email_id")
            deleted, _ = SecondaryEmail.objects.filter(
                id=secondary_email_id,
                user=request.user,
            ).delete()
            if deleted:
                messages.success(request, "Secondary email removed.")
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
