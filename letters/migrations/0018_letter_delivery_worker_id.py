import uuid

from django.db import migrations, models


def populate_delivery_worker_ids(apps, schema_editor):
    Letter = apps.get_model("letters", "Letter")

    queryset = Letter.objects.filter(delivery_worker_id__isnull=True)
    for pk in queryset.values_list("pk", flat=True).iterator(chunk_size=1000):
        Letter.objects.filter(pk=pk).update(delivery_worker_id=uuid.uuid4())


class Migration(migrations.Migration):

    dependencies = [
        ("letters", "0017_remove_is_deleted"),
    ]

    operations = [
        migrations.AddField(
            model_name="letter",
            name="delivery_worker_id",
            field=models.UUIDField(
                db_index=True,
                editable=False,
                null=True,
            ),
        ),
        migrations.RunPython(
            populate_delivery_worker_ids,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="letter",
            name="delivery_worker_id",
            field=models.UUIDField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
    ]
