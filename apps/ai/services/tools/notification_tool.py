from django.utils import timezone
from apps.notifications.models import Notification
from apps.ai.schemas import EntitySchema, ExecutionResultSchema


class NotificationTool:
    @staticmethod
    def list_notifications(user, entities: EntitySchema) -> ExecutionResultSchema:
        unread = list(Notification.objects.filter(user=user, read_at__isnull=True).order_by('-created_at')[:5])
        count = Notification.objects.filter(user=user, read_at__isnull=True).count()

        if not unread:
            return ExecutionResultSchema(
                success=True,
                action="NOTIFICATION_LIST",
                intent="NOTIFICATION_LIST",
                message="You have no unread notifications.",
                data={"unread_count": 0, "notifications": []}
            )

        items = [f"'{n.title}'" for n in unread]
        return ExecutionResultSchema(
            success=True,
            action="NOTIFICATION_LIST",
            intent="NOTIFICATION_LIST",
            message=f"You have {count} unread notification(s): {', '.join(items)}.",
            data={"unread_count": count, "notifications": [{"id": n.id, "title": n.title} for n in unread]}
        )

    @staticmethod
    def mark_as_read(user, entities: EntitySchema) -> ExecutionResultSchema:
        updated = Notification.objects.filter(user=user, read_at__isnull=True).update(read_at=timezone.now())
        return ExecutionResultSchema(
            success=True,
            action="NOTIFICATION_READ",
            intent="NOTIFICATION_READ",
            message=f"Marked {updated} notification(s) as read.",
            data={"updated_count": updated}
        )
