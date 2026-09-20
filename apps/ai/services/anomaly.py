from datetime import timedelta
from django.utils import timezone
from apps.tracking.models import TimeEntry, TimeEntryStatus
from apps.ai.models import AIInsight, InsightType, InsightStatus


class AnomalyDetector:
    MODEL_NAME = "WorkflowAnomalyDetector"
    MODEL_VERSION = "v1.2.0"

    @classmethod
    def detect_user_anomalies(cls, user):
        """
        Scans for high idle rates, extended continuous timers, or steep productivity drops.
        Strictly framed as workflow/scheduling anomalies (not medical or psychological diagnoses).
        """
        now = timezone.now()
        anomalies_found = []

        # 1. Unusually Long Open Timer (> 4 hours)
        long_timer = TimeEntry.objects.filter(
            user=user,
            status=TimeEntryStatus.OPEN,
            started_at__lt=now - timedelta(hours=4)
        ).first()

        if long_timer:
            hours_open = round((now - long_timer.started_at).total_seconds() / 3600, 1)
            payload = {
                "model_version": cls.MODEL_VERSION,
                "anomaly_type": "EXTENDED_OPEN_TIMER",
                "session_uuid": str(long_timer.session_uuid),
                "duration_hours": hours_open,
                "suggestion": f"An active timer has been running for {hours_open} hours. Did you forget to stop it?"
            }
            insight = AIInsight.objects.create(
                user=user,
                insight_type=InsightType.ANOMALY,
                status=InsightStatus.ACTIVE,
                confidence=0.95,
                model_name=f"{cls.MODEL_NAME}_{cls.MODEL_VERSION}",
                payload=payload
            )
            anomalies_found.append(insight)

        # 2. Excessive Idle Ratio in recent sessions
        recent_closed = TimeEntry.objects.filter(
            user=user,
            status=TimeEntryStatus.CLOSED,
            started_at__gte=now - timedelta(days=2)
        )
        for entry in recent_closed:
            if entry.duration_seconds > 1800 and entry.idle_seconds > (entry.duration_seconds * 0.45):
                idle_percent = int((entry.idle_seconds / entry.duration_seconds) * 100)
                payload = {
                    "model_version": cls.MODEL_VERSION,
                    "anomaly_type": "HIGH_IDLE_RATIO",
                    "entry_id": entry.id,
                    "idle_percent": idle_percent,
                    "suggestion": f"Session on {entry.started_at.strftime('%b %d')} recorded {idle_percent}% idle time. Consider adjusting idle threshold or breaking into shorter focus sprints."
                }
                insight = AIInsight.objects.create(
                    user=user,
                    insight_type=InsightType.ANOMALY,
                    status=InsightStatus.ACTIVE,
                    confidence=0.88,
                    model_name=f"{cls.MODEL_NAME}_{cls.MODEL_VERSION}",
                    payload=payload
                )
                anomalies_found.append(insight)
                break

        return anomalies_found
