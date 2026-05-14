from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("letters", "0014_auto_20260513_1739"),
    ]

    operations = [
        migrations.AddField(
            model_name="letter",
            name="total_price",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=10,
            ),
        ),
    ]
