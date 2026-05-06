from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("letters", "0006_letter_delivery_timezone"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="letter",
            name="delivery_timezone",
        ),
    ]
