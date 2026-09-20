import datetime
from django.utils import timezone
from apps.tasks.models import Task, TaskStatus
from apps.scheduling.models import ScheduleEvent, ScheduleEventType, ScheduleEventStatus
from apps.scheduling.services.scheduler import ScheduleService
from apps.ai.services.scheduler import SchedulingOptimizer
from apps.ai.schemas import EntitySchema, ExecutionResultSchema
from apps.audit.services.auditor import AuditService


class ScheduleTool:
    @staticmethod
    def create_event(user, entities: EntitySchema, resolved_task: Task = None) -> ExecutionResultSchema:
        task = resolved_task or (Task.objects.filter(id=entities.task_id).first() if entities.task_id else None)
        title = f"Focus: {task.title}" if task else (entities.task_title or "Focus Session")

        # Determine target date
        now = timezone.now()
        if entities.date:
            try:
                target_date = datetime.date.fromisoformat(entities.date)
            except Exception:
                target_date = timezone.localdate()
        else:
            target_date = timezone.localdate()

        # Determine time
        if entities.start_time:
            try:
                parts = entities.start_time.split(":")
                start_hour = int(parts[0])
                start_min = int(parts[1]) if len(parts) > 1 else 0
            except Exception:
                start_hour, start_min = 10, 0
        else:
            if entities.time_window == "AFTERNOON":
                start_hour, start_min = 14, 0
            elif entities.time_window == "EVENING":
                start_hour, start_min = 17, 30
            else:
                start_hour, start_min = 10, 0

        duration_mins = entities.duration_minutes or 60
        start_at = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time(start_hour, start_min)))
        end_at = start_at + datetime.timedelta(minutes=duration_mins)

        # Check conflicts
        conflicts = ScheduleService.detect_conflicts(user, start_at, end_at)
        if conflicts:
            conflict_names = ", ".join([f"'{c.title}' ({c.start_at.strftime('%I:%M %p')})" for c in conflicts])
            return ExecutionResultSchema(
                success=False,
                action="SCHEDULE_CREATE",
                intent="SCHEDULE_CREATE",
                message=f"Conflict detected with {conflict_names} at {start_at.strftime('%I:%M %p')}. Please select a different time.",
                data={"conflicts": [c.title for c in conflicts]}
            )

        event = ScheduleService.create_event(
            user=user,
            title=title,
            start_at=start_at,
            end_at=end_at,
            event_type=ScheduleEventType.FOCUS,
            task_id=task.id if task else None,
            source="AI"
        )

        AuditService.log(
            action='SCHEDULE_CREATED',
            user=user,
            resource_type='ScheduleEvent',
            resource_id=event.id,
            status='SUCCESS',
            metadata={'title': title, 'start_at': start_at.isoformat(), 'source': 'NLP'}
        )

        return ExecutionResultSchema(
            success=True,
            action="SCHEDULE_CREATE",
            intent="SCHEDULE_CREATE",
            message=f"Scheduled '{title}' for {start_at.strftime('%A, %b %d at %I:%M %p')} ({duration_mins} mins).",
            data={"event_id": event.id, "title": title, "start_at": start_at.isoformat(), "end_at": end_at.isoformat()},
            audit_logged=True
        )

    @staticmethod
    def update_event(user, entities: EntitySchema, resolved_event: ScheduleEvent = None) -> ExecutionResultSchema:
        event = resolved_event
        if not event and entities.task_id:
            event = ScheduleEvent.objects.filter(user=user, id=entities.task_id).first()
        if not event and entities.task_title:
            event = ScheduleEvent.objects.filter(user=user, title__icontains=entities.task_title).order_by('-start_at').first()

        if not event:
            return ExecutionResultSchema(
                success=False,
                action="SCHEDULE_UPDATE",
                intent="SCHEDULE_UPDATE",
                message="Could not find the scheduled event to update."
            )

        if entities.date or entities.start_time:
            target_date = event.start_at.date()
            if entities.date:
                try:
                    target_date = datetime.date.fromisoformat(entities.date)
                except Exception:
                    pass

            start_hour, start_min = event.start_at.hour, event.start_at.minute
            if entities.start_time:
                try:
                    parts = entities.start_time.split(":")
                    start_hour = int(parts[0])
                    start_min = int(parts[1]) if len(parts) > 1 else 0
                except Exception:
                    pass

            duration = event.end_at - event.start_at
            if entities.duration_minutes:
                duration = datetime.timedelta(minutes=entities.duration_minutes)

            new_start = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time(start_hour, start_min)))
            new_end = new_start + duration

            conflicts = ScheduleService.detect_conflicts(user, new_start, new_end, exclude_event_id=event.id)
            if conflicts:
                conflict_names = ", ".join([f"'{c.title}'" for c in conflicts])
                return ExecutionResultSchema(
                    success=False,
                    action="SCHEDULE_UPDATE",
                    intent="SCHEDULE_UPDATE",
                    message=f"Rescheduling conflict detected with {conflict_names} at {new_start.strftime('%I:%M %p')}."
                )

            event.start_at = new_start
            event.end_at = new_end

        if entities.task_title:
            event.title = entities.task_title

        event.save()

        AuditService.log(
            action='SCHEDULE_UPDATED',
            user=user,
            resource_type='ScheduleEvent',
            resource_id=event.id,
            status='SUCCESS',
            metadata={'title': event.title, 'source': 'NLP'}
        )

        return ExecutionResultSchema(
            success=True,
            action="SCHEDULE_UPDATE",
            intent="SCHEDULE_UPDATE",
            message=f"Updated scheduled event '{event.title}' to {event.start_at.strftime('%A, %b %d at %I:%M %p')}.",
            data={"event_id": event.id, "title": event.title, "start_at": event.start_at.isoformat(), "end_at": event.end_at.isoformat()},
            audit_logged=True
        )

    @staticmethod
    def delete_event(user, entities: EntitySchema, resolved_event: ScheduleEvent = None) -> ExecutionResultSchema:
        event = resolved_event
        if not event and entities.task_id:
            event = ScheduleEvent.objects.filter(user=user, id=entities.task_id).first()
        if not event and entities.task_title:
            event = ScheduleEvent.objects.filter(user=user, title__icontains=entities.task_title).order_by('-start_at').first()

        if not event:
            return ExecutionResultSchema(
                success=False,
                action="SCHEDULE_DELETE",
                intent="SCHEDULE_DELETE",
                message="Could not find the scheduled event to cancel."
            )

        title = event.title
        event_id = event.id
        event.status = ScheduleEventStatus.CANCELLED
        event.save()

        AuditService.log(
            action='SCHEDULE_DELETED',
            user=user,
            resource_type='ScheduleEvent',
            resource_id=event_id,
            status='SUCCESS',
            metadata={'title': title, 'source': 'NLP'}
        )

        return ExecutionResultSchema(
            success=True,
            action="SCHEDULE_DELETE",
            intent="SCHEDULE_DELETE",
            message=f"Cancelled scheduled event '{title}'.",
            data={"event_id": event_id, "title": title},
            audit_logged=True
        )

    @staticmethod
    def get_schedule(user, entities: EntitySchema) -> ExecutionResultSchema:
        if entities.date:
            try:
                target_date = datetime.date.fromisoformat(entities.date)
            except Exception:
                target_date = timezone.localdate()
        else:
            target_date = timezone.localdate()

        day_start = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time.min))
        day_end = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time.max))

        events = list(ScheduleService.get_user_schedule(user, day_start, day_end))
        if not events:
            return ExecutionResultSchema(
                success=True,
                action="SCHEDULE_SEARCH",
                intent="SCHEDULE_SEARCH",
                message=f"No scheduled events on {target_date.strftime('%A, %b %d')}.",
                data={"events": []}
            )

        items = [f"'{e.title}' ({e.start_at.strftime('%I:%M %p')}-{e.end_at.strftime('%I:%M %p')})" for e in events]
        return ExecutionResultSchema(
            success=True,
            action="SCHEDULE_SEARCH",
            intent="SCHEDULE_SEARCH",
            message=f"Schedule for {target_date.strftime('%b %d')}: {'; '.join(items)}.",
            data={"events": [{"id": e.id, "title": e.title, "start": e.start_at.isoformat()} for e in events]}
        )

    @staticmethod
    def check_conflicts(user, entities: EntitySchema) -> ExecutionResultSchema:
        target_date = timezone.localdate()
        start_at = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time(10, 0)))
        end_at = start_at + datetime.timedelta(minutes=60)
        conflicts = ScheduleService.detect_conflicts(user, start_at, end_at)
        if conflicts:
            return ExecutionResultSchema(
                success=True,
                action="SCHEDULE_CONFLICT_CHECK",
                intent="SCHEDULE_CONFLICT_CHECK",
                message=f"You have {len(conflicts)} conflict(s) at that time: {conflicts[0].title}."
            )
        return ExecutionResultSchema(
            success=True,
            action="SCHEDULE_CONFLICT_CHECK",
            intent="SCHEDULE_CONFLICT_CHECK",
            message="Time slot is free and clear of conflicts."
        )

    @staticmethod
    def plan_day(user, entities: EntitySchema) -> ExecutionResultSchema:
        insights = SchedulingOptimizer.optimize_schedule_for_user(user)
        if not insights:
            return ExecutionResultSchema(
                success=True,
                action="AI_SCHEDULE",
                intent="AI_SCHEDULE",
                message="Your schedule is already optimal or no pending high-priority tasks were found."
            )

        count = len(insights)
        first = insights[0]
        return ExecutionResultSchema(
            success=True,
            action="AI_SCHEDULE",
            intent="AI_SCHEDULE",
            message=f"Generated {count} AI schedule recommendation(s). Top proposal: {first.display_text}",
            data={"insights_count": count}
        )

    @staticmethod
    def get_free_slots(user, entities: EntitySchema) -> ExecutionResultSchema:
        target_date = timezone.localdate()
        day_start = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time(9, 0)))
        day_end = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time(18, 0)))
        events = ScheduleService.get_user_schedule(user, day_start, day_end)

        occupied = sum([(e.end_at - e.start_at).total_seconds() for e in events])
        free_seconds = max(0, (day_end - day_start).total_seconds() - occupied)
        free_hours = round(free_seconds / 3600, 1)

        return ExecutionResultSchema(
            success=True,
            action="AI_TIME_ALLOCATION",
            intent="AI_TIME_ALLOCATION",
            message=f"You have approximately {free_hours} hours of unallocated focus time today.",
            data={"free_hours": free_hours}
        )
