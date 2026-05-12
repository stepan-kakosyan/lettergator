from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_alter_loginevent_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="balancetransaction",
            name="external_id",
            field=models.CharField(
                blank=True,
                max_length=128,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="balancetransaction",
            name="transaction_type",
            field=models.CharField(
                choices=[
                    ("credit", "Credit"),
                    ("debit", "Debit"),
                    ("adjustment", "Adjustment"),
                ],
                default="adjustment",
                max_length=20,
            ),
        ),
    ]
