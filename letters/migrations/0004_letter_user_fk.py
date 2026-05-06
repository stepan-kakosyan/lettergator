from django.conf import settings
from django.db import migrations, models


def link_letters_to_users(apps, schema_editor):
    Letter = apps.get_model("letters", "Letter")
    CustomUser = apps.get_model("accounts", "CustomUser")

    email_to_id = {
        user.email.lower(): user.id
        for user in CustomUser.objects.exclude(email__isnull=True)
    }

    letters_to_update = []
    for letter in Letter.objects.filter(user__isnull=True):
        sender_email = (letter.sender_email or "").strip().lower()
        user_id = email_to_id.get(sender_email)
        if user_id:
            letter.user_id = user_id
            letters_to_update.append(letter)

    if letters_to_update:
        Letter.objects.bulk_update(letters_to_update, ["user"])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("letters", "0003_letter_subject_and_status_flags"),
        ("accounts", "0002_secondaryemail"),
    ]

    operations = [
        migrations.AddField(
            model_name="letter",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="letters",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(link_letters_to_users, migrations.RunPython.noop),
    ]
