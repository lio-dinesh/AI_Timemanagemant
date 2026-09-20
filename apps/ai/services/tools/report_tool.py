from django.utils import timezone
from apps.analytics.services.reports import ReportingService
from apps.notifications.services.engine import NotificationEngine
from apps.notifications.models import NotificationType, NotificationPriority
from apps.ai.schemas import EntitySchema, ExecutionResultSchema


class ReportTool:
    @staticmethod
    def generate_and_send(user, entities: EntitySchema) -> ExecutionResultSchema:
        metrics = ReportingService.get_user_dashboard_metrics(user)
        period = entities.period or "THIS_WEEK"
        tracked = metrics.get('today_tracked_hours', 0.0)
        score = metrics.get('today_score', 0.0)

        report_summary = (
            f"Productivity Report ({period}): "
            f"Logged {tracked} hours. Daily Score: {score}/100. "
            f"Pending Tasks: {metrics.get('tasks_pending', 0)}, Completed: {metrics.get('tasks_completed', 0)}."
        )

        # Dispatch through NotificationEngine (which handles Brevo email delivery if enabled)
        NotificationEngine.dispatch_dual_notifications(
            user=user,
            title=f"AI TimeSync {period.replace('_', ' ').title()} Report",
            message=report_summary,
            notification_type=NotificationType.DAILY_DIGEST,
            priority=NotificationPriority.NORMAL,
            dedupe_prefix=f"report-{user.id}-{timezone.localdate().isoformat()}"
        )

        return ExecutionResultSchema(
            success=True,
            action="REPORT_GENERATE",
            intent="REPORT_GENERATE",
            message=f"Generated {period.lower().replace('_', ' ')} report and dispatched email summary to {user.email}.",
            data={"summary": report_summary, "email": user.email}
        )

    @staticmethod
    def get_summary(user, entities: EntitySchema) -> ExecutionResultSchema:
        metrics = ReportingService.get_user_dashboard_metrics(user)
        tracked = metrics.get('today_tracked_hours', 0.0)
        score = metrics.get('today_score', 0.0)
        msg = f"Dashboard Overview: {tracked} hours tracked today (Productivity Score: {score}/100). {metrics.get('tasks_pending', 0)} task(s) in progress."
        return ExecutionResultSchema(
            success=True,
            action="REPORT_SUMMARY",
            intent="REPORT_SUMMARY",
            message=msg,
            data=metrics
        )
