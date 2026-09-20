import os
import uuid
import logging
import requests
from django.conf import settings
from django.utils import timezone
from apps.notifications.models import Notification, DeliveryStatus, NotificationProvider

logger = logging.getLogger('apps.notifications.brevo')

class BrevoEmailService:
    @classmethod
    def get_api_key(cls):
        return getattr(settings, 'BREVO_API_KEY', '') or os.environ.get('BREVO_API_KEY', '')

    @classmethod
    def get_sender_email(cls):
        return getattr(settings, 'BREVO_SENDER_EMAIL', 'noreply@aitimemanagement.com')

    @classmethod
    def get_sender_name(cls):
        return getattr(settings, 'BREVO_SENDER_NAME', 'AI Time Management')

    @classmethod
    def get_webhook_token(cls):
        return getattr(settings, 'BREVO_WEBHOOK_TOKEN', '') or os.environ.get('BREVO_WEBHOOK_TOKEN', '')

    @classmethod
    def send_transactional_email(cls, notification_id, timeout=8):
        """
        Sends transactional email via Brevo REST API (POST /v3/smtp/email).
        Updates notification record with provider_message_id, delivery_status, and timestamps.
        If no API key is provided, gracefully operates in mock/development mode.
        """
        try:
            notif = Notification.objects.get(id=notification_id)
        except Notification.DoesNotExist:
            logger.error("Notification %s not found for email dispatch", notification_id)
            return False, "Notification not found"

        api_key = cls.get_api_key()
        recipient_email = notif.recipient_email or notif.user.email
        recipient_name = notif.recipient_name or notif.user.get_full_name() or notif.user.username

        payload = {
            "sender": {
                "name": cls.get_sender_name(),
                "email": cls.get_sender_email()
            },
            "to": [
                {
                    "email": recipient_email,
                    "name": recipient_name
                }
            ],
            "subject": notif.title,
            "tags": [notif.notification_type.lower(), f"notif_{notif.id}"],
            "headers": {
                "X-Notification-ID": str(notif.id),
                "X-Dedupe-Key": str(notif.dedupe_key or "")
            }
        }

        # Use template ID if available, otherwise raw HTML/text
        if notif.provider_template_id:
            try:
                payload["templateId"] = int(notif.provider_template_id)
                payload["params"] = notif.metadata.get("template_params", {})
            except ValueError:
                payload["htmlContent"] = f"<p>{notif.message}</p>"
        else:
            payload["htmlContent"] = f"<div style='font-family: Arial, sans-serif;'><h3>{notif.title}</h3><p>{notif.message}</p></div>"
            payload["textContent"] = notif.message

        now = timezone.now()
        notif.last_attempt_at = now
        notif.retry_count += 1

        # MOCK / DEV MODE when BREVO_API_KEY is not configured
        if not api_key:
            mock_id = f"<mock-brevo-{uuid.uuid4()}@mail.local>"
            logger.info("BREVO_API_KEY unset. Simulating email dispatch for notification #%s to %s", notif.id, recipient_email)
            notif.provider = NotificationProvider.BREVO
            notif.provider_message_id = mock_id
            notif.delivery_status = DeliveryStatus.SENT
            notif.sent_at = now
            notif.save(update_fields=['provider', 'provider_message_id', 'delivery_status', 'sent_at', 'last_attempt_at', 'retry_count'])
            return True, mock_id

        headers = {
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json"
        }

        try:
            response = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                json=payload,
                headers=headers,
                timeout=timeout
            )

            if response.status_code in [200, 201, 202]:
                data = response.json()
                message_id = data.get("messageId", f"brevo-{uuid.uuid4()}")
                notif.provider = NotificationProvider.BREVO
                notif.provider_message_id = message_id
                notif.delivery_status = DeliveryStatus.SENT
                notif.sent_at = now
                notif.save(update_fields=['provider', 'provider_message_id', 'delivery_status', 'sent_at', 'last_attempt_at', 'retry_count'])
                logger.info("Brevo email dispatched successfully: %s", message_id)
                return True, message_id
            else:
                error_text = response.text[:500]
                notif.delivery_status = DeliveryStatus.FAILED
                notif.failed_at = now
                notif.failure_reason = f"Brevo HTTP {response.status_code}: {error_text}"
                notif.save(update_fields=['delivery_status', 'failed_at', 'failure_reason', 'last_attempt_at', 'retry_count'])
                logger.warning("Brevo email dispatch failed with HTTP %s", response.status_code)
                return False, notif.failure_reason

        except requests.RequestException as exc:
            notif.delivery_status = DeliveryStatus.FAILED
            notif.failed_at = now
            notif.failure_reason = f"Network exception: {str(exc)[:250]}"
            notif.save(update_fields=['delivery_status', 'failed_at', 'failure_reason', 'last_attempt_at', 'retry_count'])
            logger.error("Brevo connection error for notification #%s: %s", notif.id, str(exc))
            return False, str(exc)

    @classmethod
    def process_webhook_event(cls, event_data):
        """
        Processes incoming Brevo webhook payload idempotently.
        Maps event to notification row via message-id or tags.
        """
        message_id = event_data.get('message-id') or event_data.get('messageId')
        event_name = (event_data.get('event') or '').lower()

        if not message_id:
            # Fallback: check custom tags
            tags = event_data.get('tags', [])
            notif_tag = next((t for t in tags if t.startswith('notif_')), None)
            if notif_tag:
                notif_id = notif_tag.replace('notif_', '')
                notif = Notification.objects.filter(id=notif_id).first()
            else:
                logger.warning("Webhook received without identifiable message-id or notif tag: %s", event_data)
                return False, "Missing message identifier"
        else:
            notif = Notification.objects.filter(provider_message_id=message_id).first()

        if not notif:
            logger.info("Notification record not found for webhook message-id: %s", message_id)
            return False, "Notification not found"

        now = timezone.now()
        notif.provider_event = event_name

        # Idempotent state transitions
        if event_name in ['delivered', 'request']:
            if not notif.delivered_at:
                notif.delivered_at = now
            if notif.delivery_status not in [DeliveryStatus.OPENED, DeliveryStatus.CLICKED, DeliveryStatus.READ]:
                notif.delivery_status = DeliveryStatus.DELIVERED

        elif event_name in ['opened', 'uniqueopened']:
            if not notif.opened_at:
                notif.opened_at = now
            if not notif.delivered_at:
                notif.delivered_at = now
            if notif.delivery_status not in [DeliveryStatus.CLICKED, DeliveryStatus.READ]:
                notif.delivery_status = DeliveryStatus.OPENED

        elif event_name == 'click':
            if not notif.clicked_at:
                notif.clicked_at = now
            if not notif.opened_at:
                notif.opened_at = now
            notif.delivery_status = DeliveryStatus.CLICKED

        elif event_name in ['softbounce', 'hardbounce', 'blocked', 'spam', 'invalid']:
            if not notif.failed_at:
                notif.failed_at = now
            notif.delivery_status = DeliveryStatus.BOUNCED
            notif.failure_reason = event_data.get('reason') or f"Brevo event: {event_name}"

        elif event_name == 'error':
            if not notif.failed_at:
                notif.failed_at = now
            notif.delivery_status = DeliveryStatus.FAILED
            notif.failure_reason = event_data.get('reason') or "Brevo delivery error"

        notif.save(update_fields=[
            'delivery_status', 'provider_event', 'delivered_at',
            'opened_at', 'clicked_at', 'failed_at', 'failure_reason', 'updated_at'
        ])
        logger.info("Updated notification #%s status to %s on Brevo event '%s'", notif.id, notif.delivery_status, event_name)
        return True, "Event processed"
