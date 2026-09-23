from django.db import models
from django.conf import settings
from django.utils import timezone


class NotificationType(models.TextChoices):
    TASK_DEADLINE = 'TASK_DEADLINE', 'Task Deadline'
    TASK_ASSIGNED = 'TASK_ASSIGNED', 'Task Assigned'
    TASK_COMPLETED = 'TASK_COMPLETED', 'Task Completed'
    TASK_OVERDUE = 'TASK_OVERDUE', 'Task Overdue'
    MEETING_REMINDER = 'MEETING_REMINDER', 'Meeting Reminder'
    FOCUS_SESSION_REMINDER = 'FOCUS_SESSION_REMINDER', 'Focus Session Reminder'
    BREAK_REMINDER = 'BREAK_REMINDER', 'Break Reminder'
    DAILY_SUMMARY = 'DAILY_SUMMARY', 'Daily Summary'
    WEEKLY_SUMMARY = 'WEEKLY_SUMMARY', 'Weekly Summary'
    PRODUCTIVITY_ALERT = 'PRODUCTIVITY_ALERT', 'Productivity Alert'
    AI_RECOMMENDATION = 'AI_RECOMMENDATION', 'AI Recommendation'
    SCHEDULE_CHANGED = 'SCHEDULE_CHANGED', 'Schedule Changed'
    SECURITY_ALERT = 'SECURITY_ALERT', 'Security Alert'


class NotificationChannel(models.TextChoices):
    IN_APP = 'IN_APP', 'In-App'
    EMAIL = 'EMAIL', 'Email'


class NotificationPriority(models.TextChoices):
    LOW = 'LOW', 'Low'
    NORMAL = 'NORMAL', 'Normal'
    HIGH = 'HIGH', 'High'
    URGENT = 'URGENT', 'Urgent'


class DeliveryStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PROCESSING = 'PROCESSING', 'Processing'
    SENT = 'SENT', 'Sent'
    DELIVERED = 'DELIVERED', 'Delivered'
    OPENED = 'OPENED', 'Opened'
    CLICKED = 'CLICKED', 'Clicked'
    READ = 'READ', 'Read'
    FAILED = 'FAILED', 'Failed'
    BOUNCED = 'BOUNCED', 'Bounced'
    CANCELLED = 'CANCELLED', 'Cancelled'


class NotificationProvider(models.TextChoices):
    INTERNAL = 'INTERNAL', 'Internal'
    BREVO = 'BREVO', 'Brevo'


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True
    )
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        db_index=True
    )
    schedule_event = models.ForeignKey(
        'scheduling.ScheduleEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        db_index=True
    )

    notification_type = models.CharField(
        max_length=40,
        choices=NotificationType.choices,
        default=NotificationType.TASK_DEADLINE,
        db_index=True
    )
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        default=NotificationChannel.IN_APP,
        db_index=True
    )
    priority = models.CharField(
        max_length=20,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL
    )

    title = models.CharField(max_length=255)
    message = models.TextField()

    scheduled_for = models.DateTimeField(default=timezone.now, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    delivery_status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True
    )

    recipient_email = models.EmailField(null=True, blank=True)
    recipient_name = models.CharField(max_length=255, null=True, blank=True)

    provider = models.CharField(
        max_length=20,
        choices=NotificationProvider.choices,
        default=NotificationProvider.INTERNAL
    )
    provider_message_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    provider_template_id = models.CharField(max_length=64, null=True, blank=True)
    provider_event = models.CharField(max_length=64, null=True, blank=True)

    retry_count = models.PositiveSmallIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)

    action_url = models.CharField(max_length=500, null=True, blank=True)
    dedupe_key = models.CharField(max_length=255, null=True, blank=True, unique=True, db_index=True)

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-scheduled_for']
        indexes = [
            models.Index(fields=['user', 'delivery_status']),
            models.Index(fields=['scheduled_for', 'delivery_status']),
            models.Index(fields=['notification_type', 'channel']),
            models.Index(fields=['provider_message_id']),
        ]

    def __str__(self):
        return f"[{self.channel}][{self.delivery_status}] {self.title} to {self.user.username}"

    def mark_as_read(self):
        if not self.read_at:
            self.read_at = timezone.now()
            if self.delivery_status in [DeliveryStatus.SENT, DeliveryStatus.DELIVERED, DeliveryStatus.PENDING]:
                self.delivery_status = DeliveryStatus.READ
            self.save(update_fields=['read_at', 'delivery_status', 'updated_at'])
