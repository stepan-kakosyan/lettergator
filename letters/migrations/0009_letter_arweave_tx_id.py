from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("letters", "0008_contactticket_contactticketcomment"),
    ]

    operations = [
        migrations.AddField(
            model_name="letter",
            name="arweave_tx_id",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
