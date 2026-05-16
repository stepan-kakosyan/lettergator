from datetime import timedelta
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

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

                delivery_worker_id = letter.delivery_worker_id
                letter.delete()

            delete_mock.assert_called_once_with(delivery_worker_id)
        upsert_mock.assert_not_called()

    def test_build_schedule_item_includes_plain_message_and_recipients(self):
        letter = Letter(**self._letter_kwargs())
        letter.id = 123
        letter.delivery_worker_id = uuid.uuid4()

        item = build_schedule_item(letter)

        self.assertEqual(item["letter_id"], str(letter.delivery_worker_id))
        self.assertEqual(item["subject"], "Future Letter")
        self.assertEqual(item["recipient"], ["a@example.com", "b@example.com"])
        self.assertEqual(item["cc_email"], "sender@example.com")
        self.assertEqual(item["message"], "hello")


class LetterDeliveryStatusApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url_name = "api-letters-delivery-status"
        self.token = "worker-secret-token"

        user = get_user_model().objects.create_user(
            email="worker-test@example.com",
            full_name="Worker Test",
            password="safe-pass-123",
        )
        self.letter = Letter.objects.create(
            user=user,
            subject="Scheduled",
            sender_email="sender@example.com",
            recipient_email="recipient@example.com",
            recipient_emails=[],
            delivery_at=timezone.now() + timedelta(hours=1),
            message="hello",
        )

    def _url(self, letter_id=None):
        value = letter_id if letter_id is not None else self.letter.delivery_worker_id
        return reverse(self.url_name, kwargs={"letter_id": value})

    @patch("letters.models.upsert_letter_schedule")
    def test_patch_requires_authentication(self, upsert_mock):
        response = self.client.patch(
            self._url(),
            data={"status": "delivered"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        upsert_mock.assert_not_called()

    @patch("letters.models.upsert_letter_schedule")
    def test_patch_updates_status_without_side_effects(self, upsert_mock):
        with self.settings(DELIVERY_WORKER_TOKEN=self.token):
            response = self.client.patch(
                self._url(self.letter.delivery_worker_id),
                data={"status": "delivered"},
                format="json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.letter.refresh_from_db()
        self.assertTrue(self.letter.is_delivered)
        self.assertFalse(self.letter.has_delivery_issue)
        upsert_mock.assert_not_called()

    @patch("letters.models.upsert_letter_schedule")
    def test_patch_marks_failed_status_without_side_effects(
        self,
        upsert_mock,
    ):
        with self.settings(DELIVERY_WORKER_TOKEN=self.token):
            response = self.client.patch(
                self._url(self.letter.delivery_worker_id),
                data={"status": "failed"},
                format="json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.letter.refresh_from_db()
        self.assertFalse(self.letter.is_delivered)
        self.assertTrue(self.letter.has_delivery_issue)
        upsert_mock.assert_not_called()

    def test_patch_returns_404_when_letter_missing(self):
        import uuid
        with self.settings(DELIVERY_WORKER_TOKEN=self.token):
            response = self.client.patch(
                self._url(letter_id=uuid.uuid4()),
                data={"status": "delivered"},
                format="json",
                HTTP_X_API_KEY=self.token,
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
