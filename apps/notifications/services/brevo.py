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

        # Use template ID if available, otherwise generated HTML
        if notif.provider_template_id:
            try:
                payload["templateId"] = int(notif.provider_template_id)
                payload["params"] = notif.metadata.get("template_params", {})
            except ValueError:
                payload["htmlContent"] = cls.generate_html_email(notif)
        else:
            payload["htmlContent"] = cls.generate_html_email(notif)
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

    @classmethod
    def generate_html_email(cls, notif):
        """
        Builds a modern, premium responsive HTML email template for Brevo delivery.
        """
        badge_color = "#3b82f6"
        badge_text = notif.get_notification_type_display()
        if "ASSIGNED" in notif.notification_type:
            badge_color = "#8b5cf6"
        elif "COMPLETED" in notif.notification_type:
            badge_color = "#10b981"
        elif "OVERDUE" in notif.notification_type:
            badge_color = "#ef4444"
        elif "DEADLINE" in notif.notification_type:
            badge_color = "#f59e0b"

        action_button = ""
        if notif.action_url:
            base_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
            full_url = notif.action_url if notif.action_url.startswith('http') else f"{base_url.rstrip('/')}{notif.action_url}"
            action_button = f"""
            <div style="margin: 28px 0; text-align: center;">
                <a href="{full_url}" style="background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%); color: #ffffff; padding: 12px 28px; font-size: 14px; font-weight: 600; text-decoration: none; border-radius: 8px; display: inline-block; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);">
                    View in AI Time Management &rarr;
                </a>
            </div>
            """

        task_meta = ""
        if notif.task:
            priority_val = notif.task.priority
            priority_color = "#ef4444" if priority_val >= 9 else ("#f59e0b" if priority_val >= 7 else "#10b981")
            deadline_str = notif.task.deadline.strftime("%B %d, %Y at %I:%M %p") if notif.task.deadline else "No deadline"
            task_meta = f"""
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 20px 0;">
                <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                    <tr>
                        <td style="color: #64748b; padding: 6px 0; width: 28%;"><strong>Task:</strong></td>
                        <td style="color: #0f172a; padding: 6px 0; font-weight: 600;">{notif.task.title}</td>
                    </tr>
                    <tr>
                        <td style="color: #64748b; padding: 6px 0;"><strong>Priority:</strong></td>
                        <td style="padding: 6px 0;"><span style="background-color: {priority_color}20; color: {priority_color}; padding: 2px 8px; border-radius: 4px; font-weight: 600;">P{priority_val} / 10</span></td>
                    </tr>
                    <tr>
                        <td style="color: #64748b; padding: 6px 0;"><strong>Category:</strong></td>
                        <td style="color: #0f172a; padding: 6px 0;">{notif.task.category}</td>
                    </tr>
                    <tr>
                        <td style="color: #64748b; padding: 6px 0;"><strong>Deadline:</strong></td>
                        <td style="color: #0f172a; padding: 6px 0; font-weight: 600;">{deadline_str}</td>
                    </tr>
                </table>
            </div>
            """

        recipient = notif.recipient_email or (notif.user.email if notif.user else "")
        msg_formatted = notif.message.replace('\n', '<br>')

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{notif.title}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
<table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f1f5f9; padding: 40px 10px;">
  <tr>
    <td align="center">
      <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08);">
        <tr>
          <td style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 28px 32px; text-align: left;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td>
                  <h1 style="margin: 0; color: #ffffff; font-size: 20px; font-weight: 700; letter-spacing: -0.5px;">
                    &#9201; AI Time Management
                  </h1>
                  <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 13px;">Intelligent Productivity & Task Scheduling</p>
                </td>
                <td align="right">
                  <span style="background-color: {badge_color}; color: #ffffff; padding: 6px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">
                    {badge_text}
                  </span>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding: 32px 32px 24px 32px;">
            <h2 style="margin: 0 0 16px 0; color: #0f172a; font-size: 20px; font-weight: 700; line-height: 1.3;">
              {notif.title}
            </h2>
            <p style="margin: 0 0 20px 0; color: #334155; font-size: 15px; line-height: 1.6;">
              {msg_formatted}
            </p>
            {task_meta}
            {action_button}
          </td>
        </tr>
        <tr>
          <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 32px; text-align: center;">
            <p style="margin: 0 0 6px 0; color: #64748b; font-size: 12px;">
              This notification was generated automatically by the AI Time Management platform.
            </p>
            <p style="margin: 0; color: #94a3b8; font-size: 11px;">
              Recipient: {recipient} &bull; Powered by Gemini AI &amp; Brevo
            </p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""
        return html.strip()
