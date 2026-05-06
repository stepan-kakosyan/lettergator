from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("letters", "0005_encrypt_existing_letter_messages"),
    ]

    operations = [
        migrations.AddField(
            model_name="letter",
            name="delivery_timezone",
            field=models.CharField(default="UTC", max_length=64),
        ),
    ]
