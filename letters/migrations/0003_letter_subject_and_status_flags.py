from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("letters", "0002_letter_delivery_controls"),
    ]

    operations = [
        migrations.AddField(
            model_name="letter",
            name="subject",
            field=models.CharField(default="Untitled letter", max_length=200),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="letter",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="letter",
            name="has_delivery_issue",
            field=models.BooleanField(default=False),
        ),
    ]
