from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_customuser_balance_balancetransaction"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginEvent",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("google", "Google"),
                        ],
                        default="manual",
                        max_length=20,
                    ),
                ),
                (
                    "logged_in_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="login_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-logged_in_at"],
            },
        ),
    ]
