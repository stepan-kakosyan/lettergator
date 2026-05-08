from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_loginevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="language",
            field=models.CharField(
                choices=[
                    ("en", "English"),
                    ("ru", "Russian"),
                    ("hy", "Armenian"),
                ],
                default="en",
                max_length=5,
            ),
        ),
    ]
