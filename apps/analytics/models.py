from django.db import models
from django.conf import settings
from django.utils import timezone


class ProductivityDaily(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daily_productivity',
        db_index=True
    )
    date = models.DateField(db_index=True)

    productive_seconds = models.PositiveIntegerField(default=0)
    nonproductive_seconds = models.PositiveIntegerField(default=0)
    neutral_seconds = models.PositiveIntegerField(default=0)

    tracked_seconds = models.PositiveIntegerField(default=0)
    active_seconds = models.PositiveIntegerField(default=0)
    idle_seconds = models.PositiveIntegerField(default=0)

    focus_seconds = models.PositiveIntegerField(default=0)
    meeting_seconds = models.PositiveIntegerField(default=0)
    break_seconds = models.PositiveIntegerField(default=0)

    tasks_total = models.PositiveIntegerField(default=0)
    tasks_completed = models.PositiveIntegerField(default=0)
    tasks_overdue = models.PositiveIntegerField(default=0)

    scheduled_seconds = models.PositiveIntegerField(default=0)

    completion_rate = models.FloatField(default=0.0)
    focus_rate = models.FloatField(default=0.0)
    productivity_score = models.FloatField(default=0.0)
    efficiency_score = models.FloatField(default=0.0)

    anomaly_count = models.PositiveIntegerField(default=0)

    peak_start_time = models.TimeField(null=True, blank=True)
    peak_end_time = models.TimeField(null=True, blank=True)

    generated_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'productivity_daily'
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(fields=['user', 'date'], name='unique_user_daily_productivity')
        ]
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"DailyProd({self.user.username}, {self.date}, Score: {self.productivity_score:.1f}%)"

    @property
    def tracked_hours(self):
        return round(self.tracked_seconds / 3600, 2)

    @property
    def productive_hours(self):
        return round(self.productive_seconds / 3600, 2)

    @property
    def nonproductive_hours(self):
        return round(self.nonproductive_seconds / 3600, 2)
