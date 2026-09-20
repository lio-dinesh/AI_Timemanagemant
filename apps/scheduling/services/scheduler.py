from django.db.models import Q
from apps.scheduling.models import ScheduleEvent, ScheduleEventStatus

class ConflictError(Exception):
    pass


class ScheduleService:
    @staticmethod
    def detect_conflicts(user, start_at, end_at, exclude_event_id=None):
        """
        Detects schedule overlaps using indexed range queries:
        (event.start_at < new_end) AND (event.end_at > new_start)
        """
        qs = ScheduleEvent.objects.filter(
            user=user,
            start_at__lt=end_at,
            end_at__gt=start_at
        ).exclude(status=ScheduleEventStatus.CANCELLED)

        if exclude_event_id:
            qs = qs.exclude(id=exclude_event_id)

        return list(qs)

    @staticmethod
    def create_event(user, title, start_at, end_at, event_type="TASK", task_id=None, allow_overlap=False, description="", location="", meeting_url="", reminder_minutes=15, source="INTERNAL"):
        if end_at <= start_at:
            raise ValueError("Event end time must be after start time.")

        conflicts = ScheduleService.detect_conflicts(user, start_at, end_at)
        if conflicts and not allow_overlap:
            conflict_titles = ", ".join([f"'{c.title}' ({c.start_at.strftime('%H:%M')}-{c.end_at.strftime('%H:%M')})" for c in conflicts])
            raise ConflictError(f"Schedule conflict with existing event(s): {conflict_titles}")

        event = ScheduleEvent.objects.create(
            user=user,
            task_id=task_id,
            title=title,
            description=description,
            event_type=event_type,
            source=source,
            status=ScheduleEventStatus.SCHEDULED,
            start_at=start_at,
            end_at=end_at,
            reminder_minutes=reminder_minutes,
            location=location,
            meeting_url=meeting_url
        )
        return event

    @staticmethod
    def get_user_schedule(user, start_at, end_at):
        return ScheduleEvent.objects.filter(
            user=user,
            start_at__lt=end_at,
            end_at__gt=start_at
        ).exclude(status=ScheduleEventStatus.CANCELLED).order_by('start_at')
