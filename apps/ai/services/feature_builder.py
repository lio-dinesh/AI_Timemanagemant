import numpy as np
from datetime import timedelta
from typing import Dict, Any, List, Optional
from django.utils import timezone
from apps.analytics.models import ProductivityDaily
from apps.tracking.models import TimeEntry, TimeEntryStatus
from apps.tasks.models import Task, TaskStatus


class FeatureBuilder:
    """
    Standardized Feature Engineering and Cold-Start Handler for AI TimeSync.
    Extracts, scales, and normalizes user behavioral feature vectors.
    """

    MIN_HISTORY_DAYS = 3

    @classmethod
    def is_cold_start(cls, user) -> bool:
        count = ProductivityDaily.objects.filter(user=user).count()
        return count < cls.MIN_HISTORY_DAYS

    @classmethod
    def extract_productivity_features(cls, user, days: int = 30) -> Dict[str, Any]:
        """
        Extracts tabular features for productivity estimation.
        """
        now = timezone.now()
        start_date = (now - timedelta(days=days)).date()

        records = list(ProductivityDaily.objects.filter(
            user=user,
            date__gte=start_date
        ).order_by('date'))

        if len(records) < cls.MIN_HISTORY_DAYS:
            return {
                "is_cold_start": True,
                "history_length": len(records),
                "mean_score": 75.0,
                "score_std": 0.0,
                "mean_productive_hours": 3.5,
                "mean_idle_ratio": 0.15,
                "completion_rate": 0.80,
                "feature_vector": [75.0, 0.0, 3.5, 0.15, 0.80]
            }

        scores = [float(r.productivity_score) for r in records]
        prod_hours = [float(r.productive_seconds) / 3600.0 for r in records]
        idle_hours = [float(r.idle_seconds) / 3600.0 for r in records]
        total_hours = [float(r.total_tracked_seconds) / 3600.0 for r in records]

        idle_ratios = [
            (idle / total) if total > 0 else 0.0
            for idle, total in zip(idle_hours, total_hours)
        ]

        # Calculate task completion rate
        recent_tasks = Task.objects.filter(
            assigned_to=user,
            created_at__gte=now - timedelta(days=days)
        )
        total_tasks = recent_tasks.count()
        completed_tasks = recent_tasks.filter(status=TaskStatus.COMPLETED).count()
        completion_rate = (completed_tasks / total_tasks) if total_tasks > 0 else 0.85

        mean_score = float(np.mean(scores))
        score_std = float(np.std(scores))
        mean_prod_hours = float(np.mean(prod_hours))
        mean_idle_ratio = float(np.mean(idle_ratios))

        feature_vector = [
            round(mean_score, 2),
            round(score_std, 2),
            round(mean_prod_hours, 2),
            round(mean_idle_ratio, 2),
            round(completion_rate, 2)
        ]

        return {
            "is_cold_start": False,
            "history_length": len(records),
            "mean_score": round(mean_score, 2),
            "score_std": round(score_std, 2),
            "mean_productive_hours": round(mean_prod_hours, 2),
            "mean_idle_ratio": round(mean_idle_ratio, 2),
            "completion_rate": round(completion_rate, 2),
            "feature_vector": feature_vector
        }
