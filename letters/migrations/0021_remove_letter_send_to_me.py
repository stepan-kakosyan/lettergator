from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("letters", "0020_scheduledsms"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="letter",
            name="send_to_me",
        ),
    ]
