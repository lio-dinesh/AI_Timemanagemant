from django.db import models
from django.conf import settings
from django.utils import timezone


class InsightType(models.TextChoices):
    SCHEDULE_RECOMMENDATION = 'SCHEDULE_RECOMMENDATION', 'Schedule Recommendation'
    TIME_ALLOCATION = 'TIME_ALLOCATION', 'Time Allocation'
    PRODUCTIVITY_PREDICTION = 'PRODUCTIVITY_PREDICTION', 'Productivity Prediction'
    ANOMALY = 'ANOMALY', 'Anomaly'
    TASK_CLASSIFICATION = 'TASK_CLASSIFICATION', 'Task Classification'
    PRIORITY_RECOMMENDATION = 'PRIORITY_RECOMMENDATION', 'Priority Recommendation'
    FOCUS_RECOMMENDATION = 'FOCUS_RECOMMENDATION', 'Focus Recommendation'
    PERSONALIZED_RECOMMENDATION = 'PERSONALIZED_RECOMMENDATION', 'Personalized Recommendation'
    NLP_RESULT = 'NLP_RESULT', 'NLP Result'


class InsightStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    APPLIED = 'APPLIED', 'Applied'
    DISMISSED = 'DISMISSED', 'Dismissed'
    EXPIRED = 'EXPIRED', 'Expired'


class AIInsight(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_insights',
        db_index=True
    )
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_insights',
        db_index=True
    )
    schedule_event = models.ForeignKey(
        'scheduling.ScheduleEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_insights',
        db_index=True
    )

    insight_type = models.CharField(
        max_length=40,
        choices=InsightType.choices,
        default=InsightType.PERSONALIZED_RECOMMENDATION,
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=InsightStatus.choices,
        default=InsightStatus.ACTIVE,
        db_index=True
    )

    score = models.FloatField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)

    model_name = models.CharField(max_length=64, null=True, blank=True)
    model_version = models.CharField(max_length=32, null=True, blank=True)
    prompt_version = models.CharField(max_length=32, null=True, blank=True)

    generated_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    payload = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_insights'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'insight_type']),
            models.Index(fields=['generated_at']),
        ]

    def __str__(self):
        return f"[{self.insight_type}][{self.status}] for {self.user.username} (conf: {self.confidence})"

    @property
    def title(self):
        if not isinstance(self.payload, dict):
            return ""
        return self.payload.get("title") or ""

    @property
    def display_text(self):
        if not isinstance(self.payload, dict):
            return ""
        return (
            self.payload.get("reason")
            or self.payload.get("action_suggestion")
            or self.payload.get("suggestion")
            or self.payload.get("rationale")
            or self.payload.get("title")
            or ""
        )

    @property
    def summary(self):
        return self.display_text

    def apply(self):
        self.status = InsightStatus.APPLIED
        self.save(update_fields=['status', 'updated_at'])

    def dismiss(self):
        self.status = InsightStatus.DISMISSED
        self.save(update_fields=['status', 'updated_at'])
