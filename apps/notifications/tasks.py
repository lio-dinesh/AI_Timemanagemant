from celery import shared_task
import logging
from apps.notifications.services.brevo import BrevoEmailService
from apps.notifications.services.engine import NotificationEngine
from apps.notifications.models import Notification, DeliveryStatus, NotificationChannel

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_brevo_email(self, notification_id):
    """
    Asynchronous Celery task for Brevo transactional email delivery.
    """
    try:
        success, result = BrevoEmailService.send_transactional_email(notification_id)
        if not success and "Network exception" in str(result):
            raise self.retry(exc=Exception(result))
        return result
    except Exception as exc:
        logger.error("Error in send_brevo_email task #%s: %s", notification_id, str(exc))
        raise self.retry(exc=exc)

@shared_task
def send_notification(notification_id):
    """
    Dispatches a single notification based on its channel.
    """
    try:
        notif = Notification.objects.get(id=notification_id)
        if notif.channel == NotificationChannel.EMAIL:
            send_brevo_email.delay(notif.id)
        else:
            notif.delivery_status = DeliveryStatus.SENT
            notif.save(update_fields=['delivery_status'])
    except Notification.DoesNotExist:
        pass

@shared_task
def process_due_reminders():
    """
    Periodic Celery Beat task scanning tasks and schedule events to fire reminders.
    """
    count = NotificationEngine.scan_and_generate_reminders()
    logger.info("process_due_reminders completed: %s reminders dispatched.", count)
    return count

@shared_task
def process_brevo_event(payload):
    """
    Asynchronous task for processing incoming Brevo webhook payload idempotently.
    """
    success, msg = BrevoEmailService.process_webhook_event(payload)
    return msg
