from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.utils import timezone

from letters.models import Letter


class Command(BaseCommand):
    help = "Send due letters by datetime and mark successful ones delivered"

    def handle(self, *args, **options):
        user_model = get_user_model()
        now = timezone.now()
        due_letters = Letter.objects.filter(
            delivery_at__lte=now,
            is_delivered=False,
            is_deleted=False,
        )

        sent_count = 0
        for letter in due_letters:
            message_text = letter.get_message()
            target_emails = [letter.recipient_email, *letter.recipient_emails]
            # Preserve order and skip duplicates.
            target_emails = [
                email for i, email in enumerate(target_emails)
                if email and email not in target_emails[:i]
            ]

            all_targets_delivered = True

            for target_email in target_emails:
                fallback_emails = []
                recipient_user = user_model.objects.filter(
                    email__iexact=target_email
                ).first()
                if recipient_user:
                    fallback_emails = list(
                        recipient_user.secondary_emails.values_list(
                            "email",
                            flat=True,
                        )
                    )

                attempted_emails = [target_email, *fallback_emails]
                delivered_for_target = False

                for recipient_email in attempted_emails:
                    try:
                        send_mail(
                            subject=letter.subject,
                            message=message_text,
                            from_email=None,
                            recipient_list=[recipient_email],
                            fail_silently=False,
                        )
                        delivered_for_target = True
                        if recipient_email != target_email:
                            self.stdout.write(
                                self.style.WARNING(
                                    "Primary recipient failed; sent to "
                                    f"fallback {recipient_email}."
                                )
                            )
                        break
                    except Exception as exc:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Failed to send to {recipient_email}: {exc}"
                            )
                        )

                if not delivered_for_target:
                    all_targets_delivered = False
                    self.stderr.write(
                        self.style.ERROR(
                            "Delivery failed for all recipients of "
                            f"{target_email}."
                        )
                    )

            if all_targets_delivered and target_emails:
                letter.is_delivered = True
                letter.has_delivery_issue = False
                letter.save(update_fields=["is_delivered", "has_delivery_issue"])
                sent_count += 1
            elif not target_emails:
                letter.has_delivery_issue = True
                letter.save(update_fields=["has_delivery_issue"])
                self.stderr.write(
                    self.style.ERROR(
                        f"Letter {letter.id} has no target recipients."
                    )
                )
            else:
                letter.has_delivery_issue = True
                letter.save(update_fields=["has_delivery_issue"])

        self.stdout.write(
            self.style.SUCCESS(f"Sent {sent_count} due letter(s).")
        )
