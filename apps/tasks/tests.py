from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.tasks.models import Task, TaskStatus
from apps.tasks.services.task import TaskService

class TasksTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='t_user@example.com', username='t_user', password='pwd')
        self.task = Task.objects.create(
            title="Backend Pipeline",
            assigned_to=self.user,
            created_by=self.user,
            estimated_seconds=3600,
            deadline=timezone.now() + timedelta(days=1)
        )

    def test_task_creation_and_defaults(self):
        self.assertEqual(self.task.status, TaskStatus.TODO)
        self.assertEqual(self.task.actual_seconds, 0)
        self.assertFalse(self.task.is_overdue)

    def test_recalculate_task_actual_seconds(self):
        from apps.tracking.models import TimeEntry, TimeEntryStatus
        TimeEntry.objects.create(
            user=self.user,
            task=self.task,
            started_at=timezone.now(),
            duration_seconds=1800,
            status=TimeEntryStatus.CLOSED
        )
        TimeEntry.objects.create(
            user=self.user,
            task=self.task,
            started_at=timezone.now(),
            duration_seconds=1200,
            status=TimeEntryStatus.CLOSED
        )

        total = TaskService.recalculate_task_actual_seconds(self.task.id)
        self.assertEqual(total, 3000)

        self.task.refresh_from_db()
        self.assertEqual(self.task.actual_seconds, 3000)
        self.assertEqual(self.task.actual_hours, 0.83)
