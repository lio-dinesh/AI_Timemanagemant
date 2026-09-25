import datetime
from django.utils import timezone
from apps.scheduling.models import ScheduleEvent
from apps.notifications.models import Notification, NotificationType, NotificationPriority
from apps.notifications.services.engine import NotificationEngine
from apps.ai.schemas import EntitySchema, ExecutionResultSchema


class ReminderTool:
    @staticmethod
    def create_reminder(user, entities: EntitySchema) -> ExecutionResultSchema:
        mins = entities.reminder_minutes or 30
        now = timezone.now()
        target_title = entities.task_title or entities.extra.get('target_title') or "Upcoming Meeting"

        scheduled_for = None
        time_desc = ""

        if entities.date:
            try:
                d = datetime.date.fromisoformat(entities.date)
                hour = 10
                minute = 0
                if entities.start_time:
                    parts = entities.start_time.split(":")
                    hour = int(parts[0])
                    minute = int(parts[1]) if len(parts) > 1 else 0
                scheduled_for = timezone.make_aware(datetime.datetime.combine(d, datetime.time(hour, minute)))
                time_desc = f"tomorrow at {scheduled_for.strftime('%I:%M %p')}" if d == (timezone.localdate() + datetime.timedelta(days=1)) else f"on {scheduled_for.strftime('%A at %I:%M %p')}"
            except Exception:
                pass
        elif entities.extra.get('relative_offset'):
            try:
                scheduled_for = datetime.datetime.fromisoformat(entities.extra['relative_offset'])
                time_desc = f"in {mins} minutes"
            except Exception:
                pass

        raw_str = (entities.extra.get('raw_text') or "").lower()
        if not scheduled_for and ("in " in raw_str or (entities.reminder_minutes and not any(k in raw_str for k in ("before", "meeting")))):
            scheduled_for = now + datetime.timedelta(minutes=mins)
            time_desc = f"in {mins} minutes"

        upcoming_event = None
        if not scheduled_for or "before" in raw_str or "meeting" in target_title.lower():
            upcoming_event = ScheduleEvent.objects.filter(
                user=user,
                start_at__gte=now,
                title__icontains=target_title
            ).order_by('start_at').first()

            if not upcoming_event and ("meeting" in target_title.lower() or "before" in raw_str):
                upcoming_event = ScheduleEvent.objects.filter(
                    user=user,
                    start_at__gte=now
                ).order_by('start_at').first()

        event_info = ""
        if upcoming_event:
            event_info = f" for '{upcoming_event.title}' ({upcoming_event.start_at.strftime('%I:%M %p')})"
            if not scheduled_for:
                scheduled_for = upcoming_event.start_at - datetime.timedelta(minutes=mins)
                time_desc = f"{mins} minutes before your {target_title.lower()}"

        if not scheduled_for:
            scheduled_for = now + datetime.timedelta(minutes=mins)
            if not time_desc:
                time_desc = f"in {mins} minutes"

        dedupe_key = f"rem-{user.id}-{int(now.timestamp()) // 60}-{target_title[:10]}"
        notif = NotificationEngine.create_notification(
            user=user,
            title=f"Reminder: {target_title}",
            message=f"Reminder: {target_title}{event_info}.",
            notification_type=NotificationType.MEETING_REMINDER,
            priority=NotificationPriority.HIGH,
            schedule_event=upcoming_event,
            dedupe_key=dedupe_key,
            scheduled_for=scheduled_for
        )

        friendly_msg = f"Done! I'll remind you {time_desc} to {target_title.lower()}{event_info}."
        if "minutes before" in time_desc or "before" in raw_str:
            friendly_msg = f"Reminder successfully set for {mins} minutes before your {target_title.lower()}{event_info}."

        return ExecutionResultSchema(
            success=True,
            action="REMINDER_CREATE",
            intent="REMINDER_CREATE",
            message=friendly_msg,
            data={"notification_id": notif.id if notif else None, "minutes_before": mins, "scheduled_for": scheduled_for.isoformat()}
        )

    @staticmethod
    def list_reminders(user, entities: EntitySchema) -> ExecutionResultSchema:
        reminders = list(
            Notification.objects.filter(
                user=user,
                notification_type=NotificationType.MEETING_REMINDER,
                read_at__isnull=True
            ).order_by('-scheduled_for')[:5]
        )

        if not reminders:
            return ExecutionResultSchema(
                success=True,
                action="REMINDER_LIST",
                intent="REMINDER_LIST",
                message="You have no active meeting reminders.",
                data={"reminders": []}
            )

        items = [f"'{r.title}'" for r in reminders]
        return ExecutionResultSchema(
            success=True,
            action="REMINDER_LIST",
            intent="REMINDER_LIST",
            message=f"Active reminders: {', '.join(items)}.",
            data={"reminders": [{"id": r.id, "title": r.title} for r in reminders]}
        )

    @staticmethod
    def delete_reminder(user, entities: EntitySchema) -> ExecutionResultSchema:
        Notification.objects.filter(
            user=user,
            notification_type=NotificationType.MEETING_REMINDER,
            read_at__isnull=True
        ).update(read_at=timezone.now())
        return ExecutionResultSchema(
            success=True,
            action="REMINDER_DELETE",
            intent="REMINDER_DELETE",
            message="Dismissed active reminders."
        )
