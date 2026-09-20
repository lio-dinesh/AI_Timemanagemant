from django.db.models import Sum, Q
from django.utils import timezone
from apps.tasks.models import Task, TaskStatus

class TaskService:
    @staticmethod
    def recalculate_task_actual_seconds(task_id):
        """
        Recalculates the cached actual_seconds field from CLOSED time entries for a single task.
        """
        from apps.tracking.models import TimeEntry, TimeEntryStatus
        aggregate = TimeEntry.objects.filter(
            task_id=task_id,
            status=TimeEntryStatus.CLOSED
        ).aggregate(total_sec=Sum('duration_seconds'))

        new_total = aggregate['total_sec'] or 0
        Task.objects.filter(id=task_id).update(actual_seconds=new_total, updated_at=timezone.now())
        return new_total

    @staticmethod
    def get_user_tasks(user, status=None, project_id=None, category=None):
        """
        RBAC task query scoping:
        - Admin: all tasks
        - Manager: tasks assigned to self or subordinates, or created by self
        - Employee: tasks assigned to self or created by self
        """
        qs = Task.objects.select_related('project', 'assigned_to', 'created_by')

        if user.is_admin_role:
            pass
        elif user.is_manager_role:
            subordinate_ids = list(user.subordinates.values_list('id', flat=True))
            qs = qs.filter(Q(assigned_to=user) | Q(assigned_to_id__in=subordinate_ids) | Q(created_by=user))
        else:
            qs = qs.filter(Q(assigned_to=user) | Q(created_by=user))

        if status:
            qs = qs.filter(status=status)
        if project_id:
            qs = qs.filter(project_id=project_id)
        if category:
            qs = qs.filter(category=category)

        return qs
