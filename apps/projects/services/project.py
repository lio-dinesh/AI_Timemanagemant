from django.db.models import Count, Sum, Q
from apps.projects.models import Project, ProjectStatus

class ProjectService:
    @staticmethod
    def get_user_projects(user):
        """
        Adheres to RBAC: Employees see projects they own or tasks they are assigned to.
        Managers and Admins see team/all projects.
        """
        if user.is_admin_role:
            return Project.objects.all()
        if user.is_manager_role:
            # Manager sees own projects plus projects owned by subordinates
            subordinate_ids = list(user.subordinates.values_list('id', flat=True))
            return Project.objects.filter(Q(owner=user) | Q(owner_id__in=subordinate_ids))
        # Employee sees projects they own or where they have assigned tasks
        return Project.objects.filter(Q(owner=user) | Q(tasks__assigned_to=user)).distinct()

    @staticmethod
    def get_project_statistics(project_id):
        from apps.tasks.models import Task, TaskStatus
        stats = Task.objects.filter(project_id=project_id).aggregate(
            total_tasks=Count('id'),
            completed_tasks=Count('id', filter=Q(status=TaskStatus.COMPLETED)),
            total_estimated_seconds=Sum('estimated_seconds'),
            total_actual_seconds=Sum('actual_seconds'),
        )
        total = stats['total_tasks'] or 0
        completed = stats['completed_tasks'] or 0
        progress_percentage = int((completed / total) * 100) if total > 0 else 0
        return {
            'total_tasks': total,
            'completed_tasks': completed,
            'progress_percentage': progress_percentage,
            'total_estimated_seconds': stats['total_estimated_seconds'] or 0,
            'total_actual_seconds': stats['total_actual_seconds'] or 0,
        }
