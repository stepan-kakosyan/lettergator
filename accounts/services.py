from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.templatetags.static import static


def send_activation_email(request, user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    activation_path = reverse(
        "activate-account",
        kwargs={"uidb64": uidb64, "token": token},
    )
    activation_url = request.build_absolute_uri(activation_path)
    logo_url = request.build_absolute_uri(static("img/logo.png"))

    context = {
        "user": user,
        "activation_url": activation_url,
        "logo_url": logo_url,
        "site_name": "LetterGator",
    }

    subject = "Activate your LetterGator account"
    text_body = render_to_string(
        "accounts/emails/account_activation.txt",
        context,
    )

    html_body = render_to_string(
        "accounts/emails/account_activation.html",
        context,
    )

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
    print(message)
    print(f"Activation email sent to {user.email} with activation URL: {activation_url}")


def send_letter_created_email(request, user, letter):
    logo_url = request.build_absolute_uri(static("img/logo.png"))

    context = {
        "user": user,
        "letter": letter,
        "logo_url": logo_url,
        "site_name": "LetterGator",
    }

    subject = f"Your letter \"{letter.subject}\" is sealed and stored"
    text_body = render_to_string(
        "letters/emails/letter_created.txt",
        context,
    )
    html_body = render_to_string(
        "letters/emails/letter_created.html",
        context,
    )

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
