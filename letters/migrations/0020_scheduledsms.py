import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("letters", "0019_letter_delivery_worker_id_as_char36"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduledSMS",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("message", models.CharField(max_length=160)),
                (
                    "recipient_country_code",
                    models.CharField(
                        help_text="Dial code including + sign, e.g. +1",
                        max_length=8,
                    ),
                ),
                (
                    "recipient_local_number",
                    models.CharField(
                        help_text="Local phone number without country code",
                        max_length=20,
                    ),
                ),
                ("scheduled_at", models.DateTimeField()),
                ("can_delete_early", models.BooleanField(default=False)),
                ("can_edit_early", models.BooleanField(default=False)),
                ("allow_sender_preview", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("scheduled", "Scheduled"),
                            ("delivered", "Delivered"),
                            ("issue", "Issue"),
                        ],
                        default="scheduled",
                        max_length=20,
                    ),
                ),
                ("is_delivered", models.BooleanField(default=False)),
                ("has_delivery_issue", models.BooleanField(default=False)),
                (
                    "total_price",
                    models.DecimalField(decimal_places=2, default=0, max_digits=10),
                ),
                (
                    "idempotency_key",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=64
                    ),
                ),
                (
                    "delivery_worker_id",
                    models.CharField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        max_length=36,
                        unique=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scheduled_sms",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
