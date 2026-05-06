from django.db import migrations, models


def backfill_sender_email(apps, schema_editor):
    Letter = apps.get_model("letters", "Letter")
    for letter in Letter.objects.all():
        letter.sender_email = letter.recipient_email
        letter.save(update_fields=["sender_email"])


class Migration(migrations.Migration):
    dependencies = [
        ("letters", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="letter",
            old_name="delivery_date",
            new_name="delivery_at",
        ),
        migrations.AlterField(
            model_name="letter",
            name="delivery_at",
            field=models.DateTimeField(),
        ),
        migrations.AlterModelOptions(
            name="letter",
            options={"ordering": ["delivery_at", "created_at"]},
        ),
        migrations.AddField(
            model_name="letter",
            name="sender_email",
            field=models.EmailField(default="noreply@example.com", max_length=254),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_sender_email, migrations.RunPython.noop),
        migrations.AddField(
            model_name="letter",
            name="recipient_emails",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="letter",
            name="send_to_me",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="letter",
            name="can_delete_early",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="letter",
            name="can_edit_early",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="letter",
            name="allow_sender_preview",
            field=models.BooleanField(default=False),
        ),
    ]
