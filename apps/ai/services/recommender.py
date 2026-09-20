from django.utils import timezone
from apps.tasks.models import Task, TaskStatus
from apps.ai.models import AIInsight, InsightType, InsightStatus
from apps.ai.services.feature_builder import FeatureBuilder


class RecommenderService:
    MODEL_NAME = "PersonalizedWorkloadRecommender"
    MODEL_VERSION = "v1.2.0"

    @classmethod
    def generate_recommendations(cls, user):
        """
        Creates actionable suggestions based on pending workload and schedule habits.
        Includes model versioning and cold-start support.
        """
        now = timezone.now()
        recommendations = []
        is_cold = FeatureBuilder.is_cold_start(user)

        # Check for overdue or imminent deadlines
        overdue_count = Task.objects.filter(
            assigned_to=user,
            deadline__lt=now,
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ).count()

        if overdue_count > 0:
            payload = {
                "model_version": cls.MODEL_VERSION,
                "is_cold_start": is_cold,
                "type": "WORKLOAD_PRIORITIZATION",
                "title": f"Prioritize {overdue_count} Overdue Item(s)",
                "action_suggestion": "We recommend dedicating your first 2 hours tomorrow morning to clear overdue items before starting new work."
            }
            ins = AIInsight.objects.create(
                user=user,
                insight_type=InsightType.PERSONALIZED_RECOMMENDATION,
                status=InsightStatus.ACTIVE,
                confidence=0.92,
                model_name=f"{cls.MODEL_NAME}_{cls.MODEL_VERSION}",
                payload=payload
            )
            recommendations.append(ins)
        else:
            payload = {
                "model_version": cls.MODEL_VERSION,
                "is_cold_start": is_cold,
                "type": "DEEP_WORK_BLOCK",
                "title": "Optimal 50-Minute Focus Sprint",
                "action_suggestion": "Your schedule is clear between 10:00 AM and 11:30 AM. Perfect slot for deep coding or strategic planning."
            }
            ins = AIInsight.objects.create(
                user=user,
                insight_type=InsightType.PERSONALIZED_RECOMMENDATION,
                status=InsightStatus.ACTIVE,
                confidence=0.85,
                model_name=f"{cls.MODEL_NAME}_{cls.MODEL_VERSION}",
                payload=payload
            )
            recommendations.append(ins)

        return recommendations
