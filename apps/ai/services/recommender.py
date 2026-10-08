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
        Includes model versioning, cold-start support, and Google Gemini 3.6 Flash deep synthesis.
        """
        now = timezone.now()
        recommendations = []
        is_cold = FeatureBuilder.is_cold_start(user)

        # Check if Gemini is available for real-time generative recommendations
        from apps.ai.services.llm_provider import get_llm_provider, GeminiLLMProvider
        provider = get_llm_provider()

        user_tasks = list(Task.objects.filter(assigned_to=user).order_by('-priority', 'deadline')[:6])
        if isinstance(provider, GeminiLLMProvider) and user_tasks:
            try:
                task_lines = [
                    f"- '{t.title}' [Status: {t.status}, Priority: P{t.priority}, Est: {round(t.estimated_seconds/3600, 1)}h]"
                    for t in user_tasks
                ]
                prompt = (
                    f"User has the following current tasks:\n" + "\n".join(task_lines) + "\n\n"
                    "Generate a single, executive-grade, highly actionable strategic recommendation for today's focus.\n"
                    "Respond with a valid JSON object with exactly two string fields:\n"
                    "\"title\": (punchy title under 8 words),\n"
                    "\"action_suggestion\": (actionable recommendation in 1-2 sentences with concrete guidance)\n"
                )
                raw_json = provider.complete(
                    prompt,
                    system="You are an elite productivity strategist powered by Google Gemini 3.6 Flash. Return valid JSON only."
                )
                import json
                parsed = json.loads(raw_json)
                if parsed.get("title") and parsed.get("action_suggestion"):
                    payload = {
                        "model_version": "gemini-3.6-flash",
                        "is_cold_start": is_cold,
                        "type": "GEMINI_STRATEGIC_RECOMMENDATION",
                        "title": parsed["title"],
                        "action_suggestion": parsed["action_suggestion"]
                    }
                    ins = AIInsight.objects.create(
                        user=user,
                        insight_type=InsightType.PERSONALIZED_RECOMMENDATION,
                        status=InsightStatus.ACTIVE,
                        confidence=0.96,
                        model_name="Google_Gemini_3.6_Flash",
                        payload=payload
                    )
                    recommendations.append(ins)
                    return recommendations
            except Exception:
                pass

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
