import datetime
from django.utils import timezone
from django.db.models import Sum
from apps.tasks.models import Task
from apps.tracking.models import TimeEntry, TimeEntryStatus
from apps.tracking.services.timer import TimerService, TimerConflictError
from apps.ai.schemas import EntitySchema, ExecutionResultSchema
from apps.audit.services.auditor import AuditService


class TimeTool:
    @staticmethod
    def start_timer(user, entities: EntitySchema, resolved_task: Task = None) -> ExecutionResultSchema:
        task = resolved_task or (Task.objects.filter(id=entities.task_id).first() if entities.task_id else None)
        task_id = task.id if task else None
        activity = f"Working on {task.title}" if task else "Focus Session"

        try:
            entry = TimerService.start_timer(
                user=user,
                task_id=task_id,
                activity_type=activity
            )
            return ExecutionResultSchema(
                success=True,
                action="TIMER_START",
                intent="TIMER_START",
                message=f"Timer started for {activity}. Tracking is active.",
                data={"entry_id": entry.id, "timer_id": entry.id, "session_uuid": str(entry.session_uuid)},
                audit_logged=True
            )
        except TimerConflictError as e:
            return ExecutionResultSchema(
                success=False,
                action="TIMER_START",
                intent="TIMER_START",
                message=str(e)
            )

    @staticmethod
    def stop_timer(user, entities: EntitySchema) -> ExecutionResultSchema:
        active = TimeEntry.objects.filter(user=user, status=TimeEntryStatus.OPEN).first()
        if not active:
            return ExecutionResultSchema(
                success=False,
                action="TIMER_STOP",
                intent="TIMER_STOP",
                message="No active timer is currently running."
            )

        entry = TimerService.stop_timer(user=user, session_uuid=active.session_uuid)
        duration_mins = max(1, entry.duration_seconds // 60)
        return ExecutionResultSchema(
            success=True,
            action="TIMER_STOP",
            intent="TIMER_STOP",
            message=f"Timer stopped. Logged {duration_mins} minute(s) of focus work.",
            data={"entry_id": entry.id, "duration_seconds": entry.duration_seconds},
            audit_logged=True
        )

    @staticmethod
    def get_history(user, entities: EntitySchema) -> ExecutionResultSchema:
        entries = list(
            TimeEntry.objects.filter(user=user, status=TimeEntryStatus.CLOSED)
            .select_related('task')
            .order_by('-started_at')[:5]
        )
        if not entries:
            return ExecutionResultSchema(
                success=True,
                action="TIME_HISTORY",
                intent="TIME_HISTORY",
                message="No recent time entries found.",
                data={"entries": []}
            )

        items = []
        for e in entries:
            task_name = e.task.title if e.task else e.activity_type
            dur = max(1, e.duration_seconds // 60)
            items.append(f"{task_name} ({dur}m on {e.started_at.strftime('%b %d')})")

        return ExecutionResultSchema(
            success=True,
            action="TIME_HISTORY",
            intent="TIME_HISTORY",
            message=f"Recent sessions: {'; '.join(items)}.",
            data={"entries": [{"id": e.id, "duration": e.duration_seconds} for e in entries]}
        )

    @staticmethod
    def analyze_time(user, entities: EntitySchema) -> ExecutionResultSchema:
        now = timezone.now()
        period = entities.period or "TODAY"

        if period == "TODAY":
            start_date = timezone.localdate()
            qs = TimeEntry.objects.filter(user=user, started_at__date=start_date, status=TimeEntryStatus.CLOSED)
            label = "today"
        elif period == "THIS_WEEK":
            start_date = timezone.localdate() - datetime.timedelta(days=timezone.localdate().weekday())
            qs = TimeEntry.objects.filter(user=user, started_at__date__gte=start_date, status=TimeEntryStatus.CLOSED)
            label = "this week"
        else:
            qs = TimeEntry.objects.filter(user=user, status=TimeEntryStatus.CLOSED)
            label = "total"

        agg = qs.aggregate(
            total_sec=Sum('duration_seconds'),
            active_sec=Sum('active_seconds')
        )
        total_sec = agg['total_sec'] or 0
        hours = round(total_sec / 3600, 1)

        return ExecutionResultSchema(
            success=True,
            action="TIME_ANALYSIS",
            intent="TIME_ANALYSIS",
            message=f"You have tracked {hours} hours {label}.",
            data={"hours": hours, "total_seconds": total_sec, "period": period}
        )

    @staticmethod
    def create_manual_entry(user, entities: EntitySchema, resolved_task: Task = None) -> ExecutionResultSchema:
        task = resolved_task or (Task.objects.filter(id=entities.task_id).first() if entities.task_id else None)
        duration_mins = entities.duration_minutes or 60
        duration_sec = duration_mins * 60
        now = timezone.now()

        entry = TimeEntry.objects.create(
            user=user,
            task=task,
            activity_type=f"Manual: {task.title}" if task else "Manual Work",
            started_at=now - datetime.timedelta(minutes=duration_mins),
            ended_at=now,
            duration_seconds=duration_sec,
            active_seconds=duration_sec,
            status=TimeEntryStatus.CLOSED
        )

        return ExecutionResultSchema(
            success=True,
            action="TIME_ENTRY_CREATE",
            intent="TIME_ENTRY_CREATE",
            message=f"Logged {duration_mins} minute(s) manual time entry.",
            data={"entry_id": entry.id}
        )
