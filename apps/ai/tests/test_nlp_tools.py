from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.tasks.models import Task, TaskStatus
from apps.ai.schemas import EntitySchema
from apps.ai.services.nlp.intents import IntentType
from apps.ai.services.tools.registry import ToolRegistry
from apps.ai.services.tools.task_tool import TaskTool
from apps.ai.services.tools.time_tool import TimeTool
from apps.ai.services.tools.schedule_tool import ScheduleTool
from apps.ai.services.tools.reminder_tool import ReminderTool
from apps.ai.services.tools.analytics_tool import AnalyticsTool


class NLPToolsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='tool_user@example.com', username='tool_user', password='pwd')

    def test_task_tool_create_and_complete(self):
        # Create task
        ent_create = EntitySchema(task_title="Test Unit Suite", priority=7)
        res_create = TaskTool.create_task(self.user, ent_create)
        self.assertTrue(res_create.success)
        self.assertIn("task_id", res_create.data)
        task_id = res_create.data["task_id"]

        # Complete task
        ent_comp = EntitySchema(task_id=task_id)
        res_comp = TaskTool.complete_task(self.user, ent_comp)
        self.assertTrue(res_comp.success)

        task = Task.objects.get(id=task_id)
        self.assertEqual(task.status, TaskStatus.COMPLETED)

    def test_time_tool_start_and_stop(self):
        # Start timer
        res_start = TimeTool.start_timer(self.user, EntitySchema())
        self.assertTrue(res_start.success)
        self.assertIn("timer_id", res_start.data)

        # Stop timer
        res_stop = TimeTool.stop_timer(self.user, EntitySchema())
        self.assertTrue(res_stop.success)

    def test_schedule_tool_create_and_conflict_detection(self):
        ent = EntitySchema(task_title="Deep Work Block", start_time="11:00", duration_minutes=60)
        res1 = ScheduleTool.create_event(self.user, ent)
        self.assertTrue(res1.success)

        # Create overlapping event
        res_conflict = ScheduleTool.create_event(self.user, ent)
        self.assertFalse(res_conflict.success)
        self.assertIn("Conflict detected", res_conflict.message)

    def test_reminder_tool_create_and_list(self):
        ent = EntitySchema(task_title="Sprint Planning", reminder_minutes=15)
        res = ReminderTool.create_reminder(self.user, ent)
        self.assertTrue(res.success)

        res_list = ReminderTool.list_reminders(self.user, EntitySchema())
        self.assertTrue(res_list.success)

    def test_tool_registry_dynamic_dispatch(self):
        ent = EntitySchema(task_title="Dynamic Dispatch Task", priority=5)
        result = ToolRegistry.execute(IntentType.TASK_CREATE, self.user, ent)
        self.assertTrue(result.success)
        self.assertEqual(result.action, "TASK_CREATE")
