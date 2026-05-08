from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("letters", "0010_celerytasklog"),
    ]

    operations = [
        migrations.AddField(
            model_name="letter",
            name="idempotency_key",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=64
            ),
        ),
    ]
