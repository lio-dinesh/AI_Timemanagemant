from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.notifications.models import Notification, NotificationType, DeliveryStatus
from apps.notifications.services.engine import NotificationEngine
from apps.notifications.services.brevo import BrevoEmailService

class NotificationsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='notif@example.com', username='notif', password='pwd')

    def test_deduplication_key_prevents_duplicate_reminders(self):
        dedupe_key = f"user-{self.user.id}-task-99-deadline-24h"
        n1 = NotificationEngine.create_notification(
            user=self.user,
            title="Deadline Warning",
            message="Your task is due tomorrow",
            notification_type=NotificationType.TASK_DEADLINE,
            dedupe_key=dedupe_key
        )
        self.assertIsNotNone(n1)

        # Attempt to create duplicate with identical dedupe key
        n2 = NotificationEngine.create_notification(
            user=self.user,
            title="Duplicate Warning",
            message="Your task is due tomorrow",
            notification_type=NotificationType.TASK_DEADLINE,
            dedupe_key=dedupe_key
        )
        self.assertIsNone(n2)
        self.assertEqual(Notification.objects.filter(dedupe_key=dedupe_key).count(), 1)

    def test_brevo_email_service_and_webhook_idempotency(self):
        n = NotificationEngine.create_notification(
            user=self.user,
            title="Test Email",
            message="Test transactional message content",
            notification_type=NotificationType.TASK_DEADLINE,
        )
        # Send transactional email (runs mock in dev when key is unset)
        success, msg_id = BrevoEmailService.send_transactional_email(n.id)
        self.assertTrue(success)

        n.refresh_from_db()
        self.assertEqual(n.delivery_status, DeliveryStatus.SENT)
        self.assertIsNotNone(n.provider_message_id)

        # Process 'delivered' webhook
        event_delivered = {
            'event': 'delivered',
            'message-id': n.provider_message_id
        }
        processed, _ = BrevoEmailService.process_webhook_event(event_delivered)
        self.assertTrue(processed)

        n.refresh_from_db()
        self.assertEqual(n.delivery_status, DeliveryStatus.DELIVERED)
        original_delivered_at = n.delivered_at
        self.assertIsNotNone(original_delivered_at)

        # Deliver same webhook again (idempotency check)
        processed2, _ = BrevoEmailService.process_webhook_event(event_delivered)
        self.assertTrue(processed2)
        n.refresh_from_db()
        self.assertEqual(n.delivered_at, original_delivered_at)
