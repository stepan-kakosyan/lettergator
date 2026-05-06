from django.db import migrations


def encrypt_existing_messages(apps, schema_editor):
    Letter = apps.get_model("letters", "Letter")

    from letters.crypto import encrypt_message, is_encrypted_message

    letters_to_update = []
    for letter in Letter.objects.all().only("id", "message"):
        current_value = letter.message or ""
        if is_encrypted_message(current_value):
            continue

        letter.message = encrypt_message(current_value)
        letters_to_update.append(letter)

    if letters_to_update:
        Letter.objects.bulk_update(letters_to_update, ["message"])


class Migration(migrations.Migration):
    dependencies = [
        ("letters", "0004_letter_user_fk"),
    ]

    operations = [
        migrations.RunPython(
            encrypt_existing_messages,
            migrations.RunPython.noop,
        ),
    ]
