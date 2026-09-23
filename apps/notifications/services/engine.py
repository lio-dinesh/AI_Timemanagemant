from datetime import timedelta
from django.utils import timezone
from django.db import IntegrityError
from django.db.models import Count, Q
from apps.accounts.models import User
from apps.tasks.models import Task, TaskStatus
from apps.scheduling.models import ScheduleEvent, ScheduleEventStatus
from apps.notifications.models import (
    Notification, NotificationType, NotificationChannel,
    NotificationPriority, DeliveryStatus, NotificationProvider
)

class NotificationEngine:
    @staticmethod
    def create_notification(user, title, message, notification_type, channel=NotificationChannel.IN_APP, priority=NotificationPriority.NORMAL, task=None, schedule_event=None, dedupe_key=None, action_url=None, metadata=None):
        """
        Creates a notification with deduplication protection.
        Returns the notification if created, or None if suppressed by deduplication.
        """
        if dedupe_key:
            if Notification.objects.filter(dedupe_key=dedupe_key).exists():
                return None

        try:
            notif = Notification.objects.create(
                user=user,
                task=task,
                schedule_event=schedule_event,
                notification_type=notification_type,
                channel=channel,
                priority=priority,
                title=title,
                message=message,
                scheduled_for=timezone.now(),
                delivery_status=DeliveryStatus.PENDING,
                recipient_email=user.email if channel == NotificationChannel.EMAIL else None,
                recipient_name=user.get_full_name() or user.username,
                provider=NotificationProvider.BREVO if channel == NotificationChannel.EMAIL else NotificationProvider.INTERNAL,
                action_url=action_url,
                dedupe_key=dedupe_key,
                metadata=metadata or {}
            )
            return notif
        except IntegrityError:
            # Caught concurrent collision on unique dedupe_key
            return None

    @staticmethod
    def dispatch_dual_notifications(user, title, message, notification_type, priority=NotificationPriority.NORMAL, task=None, schedule_event=None, dedupe_prefix="", action_url=None, metadata=None):
        """
        Checks user preferences and creates separate rows for IN_APP and EMAIL channels.
        """
        prefs = user.notification_preferences or {}
        created = []

        # 1. In-App Notification
        if prefs.get('in_app_enabled', True):
            dedupe_in_app = f"{dedupe_prefix}-inapp" if dedupe_prefix else None
            n_app = NotificationEngine.create_notification(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                channel=NotificationChannel.IN_APP,
                priority=priority,
                task=task,
                schedule_event=schedule_event,
                dedupe_key=dedupe_in_app,
                action_url=action_url,
                metadata=metadata
            )
            if n_app:
                created.append(n_app)

        # 2. Email Notification (Brevo)
        if prefs.get('email_enabled', True):
            dedupe_email = f"{dedupe_prefix}-email" if dedupe_prefix else None
            n_email = NotificationEngine.create_notification(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                channel=NotificationChannel.EMAIL,
                priority=priority,
                task=task,
                schedule_event=schedule_event,
                dedupe_key=dedupe_email,
                action_url=action_url,
                metadata=metadata
            )
            if n_email:
                created.append(n_email)
                # Enqueue Celery task for email dispatch
                try:
                    from apps.notifications.tasks import send_brevo_email
                    send_brevo_email.delay(n_email.id)
                except Exception:
                    pass

        return created

    @staticmethod
    def notify_task_assigned(task, assigned_by=None):
        """
        Dispatches in-app and email notification when a task is created or assigned to a user.
        """
        user = task.assigned_to
        if not user:
            return []

        by_str = assigned_by.get_full_name() or assigned_by.username if assigned_by else "System"
        deadline_str = task.deadline.strftime('%b %d, %Y at %I:%M %p') if task.deadline else 'Not set'
        priority_label = f"P{task.priority}"
        if task.priority >= 9:
            priority_label = f"Urgent (P{task.priority})"
        elif task.priority >= 7:
            priority_label = f"High (P{task.priority})"

        title = f"New Task Assigned: {task.title}"
        message = (
            f"You have been assigned to task '{task.title}' by {by_str}.\n"
            f"Priority: {priority_label} | Category: {task.category} | Deadline: {deadline_str}."
        )

        priority = NotificationPriority.URGENT if task.priority >= 9 else (NotificationPriority.HIGH if task.priority >= 7 else NotificationPriority.NORMAL)
        prefix = f"user-{user.id}-task-{task.id}-assigned-{int(timezone.now().timestamp() // 30)}"

        return NotificationEngine.dispatch_dual_notifications(
            user=user,
            title=title,
            message=message,
            notification_type=NotificationType.TASK_ASSIGNED,
            priority=priority,
            task=task,
            dedupe_prefix=prefix,
            action_url=f"/tasks/{task.id}/",
            metadata={
                'task_id': task.id,
                'task_title': task.title,
                'priority': task.priority,
                'deadline': task.deadline.isoformat() if task.deadline else None,
                'assigned_by': by_str
            }
        )

    @staticmethod
    def notify_task_completed(task, completed_by=None):
        """
        Dispatches in-app and email notification when a task is marked as COMPLETED.
        Notifies task creator and/or assignee.
        """
        targets = set()
        if task.created_by:
            targets.add(task.created_by)
        if task.assigned_to:
            targets.add(task.assigned_to)

        by_str = completed_by.get_full_name() or completed_by.username if completed_by else "User"
        title = f"Task Completed: {task.title}"
        message = f"Task '{task.title}' has been successfully completed by {by_str}."

        created_notifs = []
        for user in targets:
            prefix = f"user-{user.id}-task-{task.id}-completed-{int(timezone.now().timestamp() // 60)}"
            res = NotificationEngine.dispatch_dual_notifications(
                user=user,
                title=title,
                message=message,
                notification_type=NotificationType.TASK_COMPLETED,
                priority=NotificationPriority.NORMAL,
                task=task,
                dedupe_prefix=prefix,
                action_url=f"/tasks/{task.id}/",
                metadata={'task_id': task.id, 'completed_by': by_str}
            )
            created_notifs.extend(res)

        return created_notifs

    @staticmethod
    def notify_task_deadline(task, window_hours=24):
        """
        Dispatches deadline reminder to task assignee.
        """
        user = task.assigned_to
        if not user:
            return []

        priority = NotificationPriority.URGENT if window_hours <= 1 else NotificationPriority.HIGH
        deadline_str = task.deadline.strftime('%b %d at %I:%M %p') if task.deadline else ''
        title = f"{'Urgent: ' if window_hours <= 1 else ''}Task Due in {window_hours} Hour{'s' if window_hours != 1 else ''}: {task.title}"
        message = f"Task '{task.title}' is due in approximately {window_hours} hour{'s' if window_hours != 1 else ''} ({deadline_str}). Please ensure progress is on track."

        prefix = f"user-{user.id}-task-{task.id}-deadline-{window_hours}h"
        return NotificationEngine.dispatch_dual_notifications(
            user=user,
            title=title,
            message=message,
            notification_type=NotificationType.TASK_DEADLINE,
            priority=priority,
            task=task,
            dedupe_prefix=prefix,
            action_url=f"/tasks/{task.id}/",
            metadata={'task_id': task.id, 'window_hours': window_hours}
        )

    @staticmethod
    def notify_task_overdue(task):
        """
        Dispatches overdue warning for tasks past deadline.
        """
        user = task.assigned_to
        if not user:
            return []

        deadline_str = task.deadline.strftime('%b %d, %Y at %I:%M %p') if task.deadline else ''
        title = f"Overdue Alert: Task '{task.title}'"
        message = f"Task '{task.title}' passed its deadline on {deadline_str} and is still pending completion. Please take action immediately."

        today_str = timezone.localdate().isoformat()
        prefix = f"user-{user.id}-task-{task.id}-overdue-{today_str}"
        return NotificationEngine.dispatch_dual_notifications(
            user=user,
            title=title,
            message=message,
            notification_type=NotificationType.TASK_OVERDUE,
            priority=NotificationPriority.URGENT,
            task=task,
            dedupe_prefix=prefix,
            action_url=f"/tasks/{task.id}/",
            metadata={'task_id': task.id, 'overdue': True}
        )

    @staticmethod
    def scan_and_generate_reminders():
        """
        Periodic scanner executed by Celery Beat:
        - Task due in 24 hours
        - Task due in 1 hour
        - Task overdue
        - Meeting starts in 15 minutes
        """
        now = timezone.now()
        generated_count = 0

        # 1. Task due in 24h (23h to 24h window)
        t_24h_min = now + timedelta(hours=23)
        t_24h_max = now + timedelta(hours=24, minutes=10)
        tasks_24h = Task.objects.filter(
            deadline__range=(t_24h_min, t_24h_max),
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ).select_related('assigned_to')

        for task in tasks_24h:
            results = NotificationEngine.notify_task_deadline(task, window_hours=24)
            generated_count += len(results)

        # 2. Task due in 1 hour (50m to 65m window)
        t_1h_min = now + timedelta(minutes=50)
        t_1h_max = now + timedelta(minutes=65)
        tasks_1h = Task.objects.filter(
            deadline__range=(t_1h_min, t_1h_max),
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ).select_related('assigned_to')

        for task in tasks_1h:
            results = NotificationEngine.notify_task_deadline(task, window_hours=1)
            generated_count += len(results)

        # 3. Overdue Tasks (deadline in past, not completed or cancelled)
        overdue_tasks = Task.objects.filter(
            deadline__lt=now,
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ).select_related('assigned_to')[:50]

        for task in overdue_tasks:
            results = NotificationEngine.notify_task_overdue(task)
            generated_count += len(results)

        # 4. Schedule Event starting in 15 minutes (10m to 20m window)
        m_15_min = now + timedelta(minutes=10)
        m_15_max = now + timedelta(minutes=20)
        events_15m = ScheduleEvent.objects.filter(
            start_at__range=(m_15_min, m_15_max),
            status=ScheduleEventStatus.SCHEDULED
        ).select_related('user')

        for ev in events_15m:
            user = ev.user
            prefix = f"user-{user.id}-event-{ev.id}-reminder-15m"
            results = NotificationEngine.dispatch_dual_notifications(
                user=user,
                title=f"Upcoming Event: {ev.title}",
                message=f"{ev.get_event_type_display()} starts in 15 minutes at {ev.start_at.strftime('%H:%M')}.",
                notification_type=NotificationType.MEETING_REMINDER,
                priority=NotificationPriority.NORMAL,
                schedule_event=ev,
                dedupe_prefix=prefix,
                action_url="/schedule/"
            )
            generated_count += len(results)

        return generated_count

    @staticmethod
    def get_notification_analytics(user=None):
        """
        Calculates delivery rate, open rate, click rate, and breakdown by channel and type.
        """
        qs = Notification.objects.all()
        if user and not user.is_admin_role:
            qs = qs.filter(user=user)

        total = qs.count()
        if total == 0:
            return {
                'total': 0, 'sent': 0, 'delivered': 0, 'opened': 0,
                'clicked': 0, 'read': 0, 'failed': 0, 'bounced': 0,
                'delivery_rate': 0.0, 'open_rate': 0.0, 'click_rate': 0.0,
                'failure_rate': 0.0, 'by_type': [], 'by_channel': []
            }

        counts = qs.aggregate(
            sent=Count('id', filter=Q(delivery_status__in=[DeliveryStatus.SENT, DeliveryStatus.DELIVERED, DeliveryStatus.OPENED, DeliveryStatus.CLICKED, DeliveryStatus.READ])),
            delivered=Count('id', filter=Q(delivery_status__in=[DeliveryStatus.DELIVERED, DeliveryStatus.OPENED, DeliveryStatus.CLICKED, DeliveryStatus.READ])),
            opened=Count('id', filter=Q(delivery_status__in=[DeliveryStatus.OPENED, DeliveryStatus.CLICKED, DeliveryStatus.READ])),
            clicked=Count('id', filter=Q(delivery_status=DeliveryStatus.CLICKED)),
            read=Count('id', filter=Q(delivery_status=DeliveryStatus.READ)),
            failed=Count('id', filter=Q(delivery_status=DeliveryStatus.FAILED)),
            bounced=Count('id', filter=Q(delivery_status=DeliveryStatus.BOUNCED)),
        )

        sent = counts['sent'] or 0
        delivered = counts['delivered'] or 0
        opened = counts['opened'] or 0
        clicked = counts['clicked'] or 0
        failed = counts['failed'] or 0
        bounced = counts['bounced'] or 0
        read = counts['read'] or 0

        delivery_rate = round((delivered / sent * 100), 1) if sent > 0 else 0.0
        open_rate = round((opened / delivered * 100), 1) if delivered > 0 else 0.0
        click_rate = round((clicked / opened * 100), 1) if opened > 0 else 0.0
        failure_rate = round(((failed + bounced) / total * 100), 1) if total > 0 else 0.0

        by_type = list(qs.values('notification_type').annotate(count=Count('id')).order_by('-count'))
        by_channel = list(qs.values('channel').annotate(count=Count('id')).order_by('-count'))

        return {
            'total': total,
            'sent': sent,
            'delivered': delivered,
            'opened': opened,
            'clicked': clicked,
            'read': read,
            'failed': failed,
            'bounced': bounced,
            'delivery_rate': delivery_rate,
            'open_rate': open_rate,
            'click_rate': click_rate,
            'failure_rate': failure_rate,
            'by_type': by_type,
            'by_channel': by_channel,
        }
