import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class TimeEntryStatus(models.TextChoices):
    OPEN = 'OPEN', 'Open'
    CLOSED = 'CLOSED', 'Closed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class TimeEntrySource(models.TextChoices):
    MANUAL = 'MANUAL', 'Manual'
    AUTOMATIC = 'AUTOMATIC', 'Automatic'
    IMPORTED = 'IMPORTED', 'Imported'


class TrackingMethod(models.TextChoices):
    TIMER = 'TIMER', 'Timer'
    DESKTOP = 'DESKTOP', 'Desktop'
    BROWSER = 'BROWSER', 'Browser'
    MOBILE = 'MOBILE', 'Mobile'
    SYSTEM = 'SYSTEM', 'System'


class ProductivityCategory(models.TextChoices):
    PRODUCTIVE = 'PRODUCTIVE', 'Productive'
    NEUTRAL = 'NEUTRAL', 'Neutral'
    DISTRACTION = 'DISTRACTION', 'Distraction'
    UNKNOWN = 'UNKNOWN', 'Unknown'


class TimeEntry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='time_entries',
        db_index=True
    )
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='time_entries',
        db_index=True
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='time_entries',
        db_index=True
    )

    session_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    duration_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Materialized total elapsed seconds calculated server-side"
    )
    active_seconds = models.PositiveIntegerField(default=0)
    idle_seconds = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=TimeEntryStatus.choices,
        default=TimeEntryStatus.OPEN,
        db_index=True
    )
    source = models.CharField(
        max_length=20,
        choices=TimeEntrySource.choices,
        default=TimeEntrySource.MANUAL
    )
    tracking_method = models.CharField(
        max_length=20,
        choices=TrackingMethod.choices,
        default=TrackingMethod.TIMER
    )

    activity_type = models.CharField(max_length=64, default='Work')
    application_name = models.CharField(max_length=128, null=True, blank=True)
    domain_name = models.CharField(max_length=128, null=True, blank=True)

    productivity_category = models.CharField(
        max_length=20,
        choices=ProductivityCategory.choices,
        default=ProductivityCategory.PRODUCTIVE,
        db_index=True
    )
    classification_confidence = models.FloatField(default=1.0)

    notes = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'time_entries'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', 'started_at']),
            models.Index(fields=['task', 'started_at']),
            models.Index(fields=['project', 'started_at']),
            models.Index(fields=['user', 'productivity_category', 'started_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"TimeEntry({self.user.username}, {self.session_uuid}, {self.status}, {self.duration_seconds}s)"

    @property
    def formatted_duration(self):
        seconds = self.duration_seconds
        if self.status == TimeEntryStatus.OPEN and not seconds:
            seconds = int((timezone.now() - self.started_at).total_seconds())
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
