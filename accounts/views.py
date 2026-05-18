from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.db import transaction as db_transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils import translation
from django.utils.encoding import force_str
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST
from django.conf import settings

from .forms import EmailAuthenticationForm, TestEmailForm, UserRegistrationForm
from .google_auth import exchange_code_for_user_info, generate_state, get_authorization_url
from .models import BalanceTransaction, CustomUser, LoginEvent
from .services import send_activation_email
from .tasks import send_pending_email_confirmation_task


def register_view(request):
    if request.user.is_authenticated:
        if request.headers.get("HX-Request") == "true":
            return HttpResponse(
                status=204,
                headers={"HX-Redirect": reverse("landing-page")},
            )
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

        if request.headers.get("HX-Request") == "true":
            return HttpResponse(
                status=204,
                headers={"HX-Redirect": reverse("dashboard_view")},
            )
        return redirect("dashboard_view")

    return render(request, "accounts/register.html", {"form": form})


class EmailLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("landing-page")

    def form_valid(self, form):
        response = super().form_valid(form)
        LoginEvent.objects.create(
            user=self.request.user,
            method=LoginEvent.Method.MANUAL,
        )
        if self.request.headers.get("HX-Request") == "true":
            return HttpResponse(
                status=204,
                headers={"HX-Redirect": str(self.get_success_url())},
            )
        return response


def logout_view(request):
    logout(request)
    return redirect("landing-page")


_VALID_LANGS = {"en", "ru", "hy"}


def set_language_view(request):
    """Switch UI language. Saves to user.language for logged-in users;
    always sets Django's language cookie for guests."""
    lang = request.GET.get("lang", "en")
    if lang not in _VALID_LANGS:
        lang = "en"

    if request.user.is_authenticated:
        request.user.language = lang
        request.user.save(update_fields=["language"])

    referer = request.META.get("HTTP_REFERER", "/")
    if not url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        referer = "/"

    response = redirect(referer)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        lang,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        path=settings.LANGUAGE_COOKIE_PATH,
        domain=settings.LANGUAGE_COOKIE_DOMAIN,
        secure=settings.LANGUAGE_COOKIE_SECURE,
        samesite=settings.LANGUAGE_COOKIE_SAMESITE,
    )
    translation.activate(lang)
    return response


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

    if not already_verified:
        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            gift_amount = 2
            user.balance += gift_amount
            user.save(update_fields=["balance"])
            BalanceTransaction.objects.create(
                user=user,
                amount=gift_amount,
                transaction_type=BalanceTransaction.TYPE_CREDIT,
                reason="Welcome gift for email verification",
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
        try:
            send_pending_email_confirmation_task(
                user.id,
                request.build_absolute_uri("/"),
            )
            messages.success(
                request,
                "Confirmation email has been sent to your pending address.",
            )
        except Exception:
            messages.error(
                request,
                "Unable to send confirmation email right now.",
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
def test_email_view(request):
    initial_data = {
        "to_email": request.user.email,
        "subject": "LetterGator test email",
        "message": "If you received this email, delivery is working.",
    }

    form = TestEmailForm(request.POST or None, initial=initial_data)

    if request.method == "POST" and form.is_valid():
        # try:
        send_mail(
            subject=form.cleaned_data["subject"],
            message=form.cleaned_data["message"],
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[form.cleaned_data["to_email"]],
            fail_silently=False,
        )
        messages.success(request, "Test email sent successfully.")
        return redirect("test-email")
        # except Exception as exc:
        #     messages.error(
        #         request,
        #         f"Unable to send test email: {exc}",
        #     )

    return render(request, "accounts/test_email.html", {"form": form})


def _google_redirect_uri(request):
    return request.build_absolute_uri(reverse("google-callback"))


def google_login_view(request):
    """Redirect user to Google's OAuth2 authorization page."""
    if request.user.is_authenticated:
        return redirect("landing-page")
    state = generate_state()
    request.session["google_oauth_state"] = state
    redirect_uri = _google_redirect_uri(request)
    return redirect(get_authorization_url(redirect_uri, state))


def google_callback_view(request):
    """Handle the OAuth2 callback from Google."""
    error = request.GET.get("error")
    if error:
        messages.error(request, f"Google sign-in was cancelled or failed: {error}")
        return redirect("login")

    state = request.GET.get("state", "")
    stored_state = request.session.pop("google_oauth_state", None)
    if not stored_state or state != stored_state:
        messages.error(request, "Invalid OAuth state. Please try again.")
        return redirect("login")

    code = request.GET.get("code")
    if not code:
        messages.error(request, "No authorisation code received from Google.")
        return redirect("login")

    try:
        redirect_uri = _google_redirect_uri(request)
        user_info = exchange_code_for_user_info(code, redirect_uri)
    except ValueError as exc:
        messages.error(request, f"Google sign-in failed: {exc}")
        return redirect("login")

    email = (user_info.get("email") or "").strip().lower()
    if not email:
        messages.error(request, "Google did not return an email address.")
        return redirect("login")

    full_name = (
        user_info.get("name")
        or user_info.get("given_name")
        or email.split("@")[0]
    ).strip()

    user = CustomUser.objects.filter(email=email).first()
    is_new = user is None

    if is_new:
        with db_transaction.atomic():
            user = CustomUser(
                email=email,
                full_name=full_name,
                email_verified=True,
                email_verified_at=timezone.now(),
            )
            user.set_unusable_password()
            user.balance = 2
            user.save()
            BalanceTransaction.objects.create(
                user=user,
                amount=2,
                transaction_type=BalanceTransaction.TYPE_CREDIT,
                reason="Welcome gift for email verification",
            )
    else:
        # Ensure email is marked verified for existing users logging in via Google
        if not user.email_verified:
            user.email_verified = True
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified", "email_verified_at"])

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    LoginEvent.objects.create(user=user, method=LoginEvent.Method.GOOGLE)

    if is_new:
        messages.success(
            request,
            "Account created with Google. Welcome — $2.00 has been added to your balance!",
        )
    else:
        messages.success(request, "Signed in with Google.")

    return redirect("landing-page")
