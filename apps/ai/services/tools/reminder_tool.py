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
        upcoming_event = ScheduleEvent.objects.filter(
            user=user,
            start_at__gte=now,
            title__icontains=target_title
        ).order_by('start_at').first()

        if not upcoming_event:
            upcoming_event = ScheduleEvent.objects.filter(
                user=user,
                start_at__gte=now
            ).order_by('start_at').first()

        event_info = ""
        if upcoming_event:
            event_info = f" for '{upcoming_event.title}' ({upcoming_event.start_at.strftime('%I:%M %p')})"

        dedupe_key = f"rem-{user.id}-{int(now.timestamp()) // 300}"
        notif = NotificationEngine.create_notification(
            user=user,
            title=f"Reminder: {target_title}",
            message=f"Reminder alert set {mins} minutes before your {target_title.lower()}{event_info}.",
            notification_type=NotificationType.MEETING_REMINDER,
            priority=NotificationPriority.HIGH,
            schedule_event=upcoming_event,
            dedupe_key=dedupe_key
        )

        return ExecutionResultSchema(
            success=True,
            action="REMINDER_CREATE",
            intent="REMINDER_CREATE",
            message=f"Reminder successfully set for {mins} minutes before your {target_title.lower()}{event_info}.",
            data={"notification_id": notif.id if notif else None, "minutes_before": mins}
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
