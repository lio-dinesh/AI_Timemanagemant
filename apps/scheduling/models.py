from django.db import models
from django.conf import settings
from django.utils import timezone


class ScheduleEventType(models.TextChoices):
    TASK = 'TASK', 'Task'
    MEETING = 'MEETING', 'Meeting'
    FOCUS = 'FOCUS', 'Focus Session'
    BREAK = 'BREAK', 'Break'
    PERSONAL = 'PERSONAL', 'Personal'


class ScheduleEventSource(models.TextChoices):
    INTERNAL = 'INTERNAL', 'Internal'
    AI = 'AI', 'AI Scheduled'
    GOOGLE = 'GOOGLE', 'Google Calendar'
    OUTLOOK = 'OUTLOOK', 'Outlook Calendar'


class ScheduleEventStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', 'Scheduled'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class ScheduleEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='schedule_events',
        db_index=True
    )
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_events',
        db_index=True
    )

    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    event_type = models.CharField(
        max_length=20,
        choices=ScheduleEventType.choices,
        default=ScheduleEventType.TASK,
        db_index=True
    )
    source = models.CharField(
        max_length=20,
        choices=ScheduleEventSource.choices,
        default=ScheduleEventSource.INTERNAL
    )
    external_provider = models.CharField(max_length=64, null=True, blank=True)
    external_id = models.CharField(max_length=255, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=ScheduleEventStatus.choices,
        default=ScheduleEventStatus.SCHEDULED,
        db_index=True
    )

    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField(db_index=True)

    recurrence_rule = models.CharField(max_length=128, null=True, blank=True)
    recurrence_until = models.DateTimeField(null=True, blank=True)

    reminder_minutes = models.PositiveIntegerField(null=True, blank=True, default=15)

    location = models.CharField(max_length=255, null=True, blank=True)
    meeting_url = models.URLField(max_length=500, null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'schedule_events'
        ordering = ['start_at']
        indexes = [
            models.Index(fields=['user', 'start_at']),
            models.Index(fields=['user', 'end_at']),
            models.Index(fields=['user', 'start_at', 'end_at']),
            models.Index(fields=['task']),
            models.Index(fields=['external_provider', 'external_id']),
        ]

    def __str__(self):
        return f"[{self.event_type}] {self.title} ({self.start_at:%Y-%m-%d %H:%M} to {self.end_at:%H:%M})"

    @property
    def duration_minutes(self):
        return int((self.end_at - self.start_at).total_seconds() / 60)
