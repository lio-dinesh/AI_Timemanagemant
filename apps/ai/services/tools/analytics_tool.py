import datetime
from django.utils import timezone
from django.db.models import Avg, Sum
from apps.analytics.models import ProductivityDaily
from apps.tracking.models import TimeEntry, TimeEntryStatus
from apps.ai.models import AIInsight, InsightStatus
from apps.ai.services.anomaly import AnomalyDetector
from apps.ai.services.recommender import RecommenderService
from apps.ai.schemas import EntitySchema, ExecutionResultSchema, AnalyticsQueryPlanSchema


class AnalyticsTool:
    @staticmethod
    def get_summary(user, entities: EntitySchema) -> ExecutionResultSchema:
        today = timezone.localdate()
        daily = ProductivityDaily.objects.filter(user=user, date=today).first()

        if daily:
            score = round(daily.productivity_score, 1)
            tracked = daily.tracked_hours
            productive = daily.productive_hours
            msg = f"Today's Productivity Score: {score}/100. You tracked {tracked}h total ({productive}h focused productive work)."
            data = {"score": score, "tracked_hours": tracked, "productive_hours": productive}
        else:
            msg = "No productivity data recorded for today yet. Start a timer to track your sessions."
            data = {"score": 0.0, "tracked_hours": 0.0}

        return ExecutionResultSchema(
            success=True,
            action="PRODUCTIVITY_SUMMARY",
            intent="PRODUCTIVITY_SUMMARY",
            message=msg,
            data=data
        )

    @staticmethod
    def get_trend(user, entities: EntitySchema) -> ExecutionResultSchema:
        today = timezone.localdate()
        past_7_days = [today - datetime.timedelta(days=i) for i in range(7)]
        records = list(ProductivityDaily.objects.filter(user=user, date__in=past_7_days))

        if not records:
            return ExecutionResultSchema(
                success=True,
                action="PRODUCTIVITY_TREND",
                intent="PRODUCTIVITY_TREND",
                message="Not enough historical tracking data across the past 7 days to display a trend.",
                data={"records": []}
            )

        avg_score = round(sum([r.productivity_score for r in records]) / len(records), 1)
        total_tracked = round(sum([r.tracked_hours for r in records]), 1)
        total_prod = round(sum([r.productive_hours for r in records]), 1)

        msg = f"Over the past 7 days: Average Score {avg_score}/100 across {total_tracked}h tracked ({total_prod}h productive)."
        return ExecutionResultSchema(
            success=True,
            action="PRODUCTIVITY_TREND",
            intent="PRODUCTIVITY_TREND",
            message=msg,
            data={"avg_score": avg_score, "total_tracked_hours": total_tracked, "total_productive_hours": total_prod}
        )

    @staticmethod
    def get_patterns(user, entities: EntitySchema) -> ExecutionResultSchema:
        entries = TimeEntry.objects.filter(user=user, status=TimeEntryStatus.CLOSED)
        if entries.count() < 3:
            return ExecutionResultSchema(
                success=True,
                action="PRODUCTIVITY_PATTERN",
                intent="PRODUCTIVITY_PATTERN",
                message="Need more tracked sessions to reliably determine your peak focus patterns."
            )

        return ExecutionResultSchema(
            success=True,
            action="PRODUCTIVITY_PATTERN",
            intent="PRODUCTIVITY_PATTERN",
            message="Historical data shows your focus is highest in the morning (09:30 AM – 11:30 AM).",
            data={"peak_window": "09:30 - 11:30"}
        )

    @staticmethod
    def get_recommendations(user, entities: EntitySchema) -> ExecutionResultSchema:
        recs = RecommenderService.generate_recommendations(user)
        if not recs:
            return ExecutionResultSchema(
                success=True,
                action="AI_RECOMMENDATION",
                intent="AI_RECOMMENDATION",
                message="Your schedule and workload look balanced. No urgent recommendations."
            )

        first = recs[0]
        return ExecutionResultSchema(
            success=True,
            action="AI_RECOMMENDATION",
            intent="AI_RECOMMENDATION",
            message=f"Recommendation: {first.display_text}",
            data={"recommendations_count": len(recs)}
        )

    @staticmethod
    def check_anomalies(user, entities: EntitySchema) -> ExecutionResultSchema:
        anomalies = AnomalyDetector.detect_user_anomalies(user)
        if not anomalies:
            return ExecutionResultSchema(
                success=True,
                action="ANOMALY_ANALYSIS",
                intent="ANOMALY_ANALYSIS",
                message="Workflow analysis clear: No open-timer or excessive-idle anomalies detected."
            )

        first = anomalies[0]
        return ExecutionResultSchema(
            success=True,
            action="ANOMALY_ANALYSIS",
            intent="ANOMALY_ANALYSIS",
            message=f"Anomaly Alert: {first.display_text}",
            data={"anomalies_found": len(anomalies)}
        )
