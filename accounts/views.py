from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST

from .forms import EmailAuthenticationForm, UserRegistrationForm
from .models import CustomUser
from .services import send_activation_email
from .tasks import send_pending_email_confirmation_task


def register_view(request):
    if request.user.is_authenticated:
        return redirect("landing-page")

    form = UserRegistrationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.email_verified = False
        user.email_verified_at = None
        user.save()

        # Login first so token generation reflects the latest login state.
        login(request, user)

        try:
            send_activation_email(request, user)
            messages.success(
                request,
                "Activation email sent. Verify your inbox to unlock letter creation.",
            )
        except Exception:
            messages.error(
                request,
                "Account created, but activation email could not be sent.",
            )

        return redirect("dashboard_view")

    return render(request, "accounts/register.html", {"form": form})


class EmailLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("landing-page")


def logout_view(request):
    logout(request)
    return redirect("landing-page")


def activate_account_view(request, uidb64, token):
    user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    if not user or not default_token_generator.check_token(user, token):
        return render(request, "accounts/activation_invalid.html")

    already_verified = user.email_verified
    user.email_verified = True
    user.email_verified_at = timezone.now()
    user.email_reactivation_sent_at = None
    user.save(
        update_fields=[
            "email_verified",
            "email_verified_at",
            "email_reactivation_sent_at",
        ]
    )

    context = {
        "already_verified": already_verified,
    }
    return render(request, "accounts/activation_success.html", context)


def confirm_pending_email_view(request, uidb64, token):
    user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    if not user or not default_token_generator.check_token(user, token):
        return render(request, "accounts/activation_invalid.html")

    if not user.pending_email:
        return render(request, "accounts/activation_invalid.html")

    user.email = user.pending_email
    user.pending_email = ""
    user.pending_email_requested_at = None
    user.email_verified = True
    user.email_verified_at = timezone.now()
    user.email_reactivation_sent_at = None
    user.save(
        update_fields=[
            "email",
            "pending_email",
            "pending_email_requested_at",
            "email_verified",
            "email_verified_at",
            "email_reactivation_sent_at",
        ]
    )

    return render(request, "accounts/activation_success.html")


@login_required
@require_POST
def resend_activation_email_view(request):
    user = request.user

    if user.email_verified:
        messages.info(request, "Your email is already verified.")
    else:
        try:
            send_activation_email(request, user)
            messages.success(request, "Activation email was sent again.")
        except Exception:
            messages.error(
                request,
                "Unable to resend activation email right now.",
            )

    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("dashboard_view")


@login_required
@require_POST
def resend_pending_email_confirmation_view(request):
    user = request.user

    if not user.pending_email:
        messages.info(request, "No pending email change found.")
    else:
        send_pending_email_confirmation_task.delay(
            user.id,
            request.build_absolute_uri("/"),
        )
        messages.success(
            request,
            "Confirmation email has been queued for your pending address.",
        )

    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("dashboard_view")
