from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .dynamodb_sync import build_schedule_item
from .models import Letter


class LetterDynamoSyncTests(TestCase):
    def _letter_kwargs(self):
        return {
            "subject": "Future Letter",
            "sender_email": "sender@example.com",
            "recipient_email": "a@example.com",
            "recipient_emails": [
                "a@example.com",
                "b@example.com",
                "b@example.com",
                "",
            ],
            "delivery_at": timezone.now() + timedelta(days=1),
            "message": "hello",
        }

    def test_save_upserts_schedule_on_commit(self):
        letter = Letter(**self._letter_kwargs())
        with patch("letters.models.upsert_letter_schedule") as upsert_mock:
            with patch("letters.models.delete_letter_schedule") as delete_mock:
                with self.captureOnCommitCallbacks(execute=True):
                    letter.save()

        upsert_mock.assert_called_once_with(letter)
        delete_mock.assert_not_called()

    def test_delete_removes_schedule_from_dynamodb(self):
        with patch("letters.models.upsert_letter_schedule") as upsert_mock:
            with patch("letters.models.delete_letter_schedule") as delete_mock:
                with self.captureOnCommitCallbacks(execute=True):
                    letter = Letter.objects.create(**self._letter_kwargs())

                upsert_mock.assert_called_once_with(letter)
                upsert_mock.reset_mock()
                delete_mock.reset_mock()

                letter_id = letter.id
                letter.delete()

        delete_mock.assert_called_once_with(letter_id)
        upsert_mock.assert_not_called()

    def test_build_schedule_item_includes_plain_message_and_recipients(self):
        letter = Letter(**self._letter_kwargs())
        letter.id = 123

        item = build_schedule_item(letter)

        self.assertEqual(item["letter_id"], "123")
        self.assertEqual(item["subject"], "Future Letter")
        self.assertEqual(item["recipient"], ["a@example.com", "b@example.com"])
        self.assertEqual(item["cc_email"], "sender@example.com")
        self.assertEqual(item["message"], "hello")
