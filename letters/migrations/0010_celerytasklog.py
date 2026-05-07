from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("letters", "0009_letter_arweave_tx_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="CeleryTaskLog",
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
                ("task_name", models.CharField(max_length=200)),
                (
                    "task_id",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("started", "Started"),
                            ("success", "Success"),
                            ("failure", "Failure"),
                        ],
                        default="started",
                        max_length=20,
                    ),
                ),
                ("detail", models.TextField(blank=True, default="")),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                (
                    "finished_at",
                    models.DateTimeField(blank=True, null=True),
                ),
            ],
            options={
                "ordering": ["-started_at"],
            },
        ),
    ]
