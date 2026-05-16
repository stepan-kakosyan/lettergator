import uuid

from django.db import migrations, models


def normalize_delivery_worker_ids(apps, schema_editor):
    Letter = apps.get_model("letters", "Letter")

    for letter in Letter.objects.only("id", "delivery_worker_id").iterator(
        chunk_size=1000,
    ):
        value = (letter.delivery_worker_id or "").strip()
        if not value:
            continue

        try:
            canonical = str(uuid.UUID(value))
        except (TypeError, ValueError, AttributeError):
            continue

        if canonical != value:
            Letter.objects.filter(pk=letter.pk).update(
                delivery_worker_id=canonical
            )


class Migration(migrations.Migration):

    dependencies = [
        ("letters", "0018_letter_delivery_worker_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="letter",
            name="delivery_worker_id",
            field=models.CharField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                max_length=36,
                unique=True,
            ),
        ),
        migrations.RunPython(
            normalize_delivery_worker_ids,
            migrations.RunPython.noop,
        ),
    ]
