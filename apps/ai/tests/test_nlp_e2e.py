import datetime
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.tasks.models import Task, TaskStatus
from apps.ai.services.nlp.service import NLPCommandService


class NLPE2ETestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='e2e_user@example.com',
            username='e2e_user',
            password='pwd'
        )
        now = timezone.now()
        self.task1 = Task.objects.create(
            title="Refactor Query Pipeline",
            assigned_to=self.user,
            created_by=self.user,
            priority=8,
            deadline=now + datetime.timedelta(days=2),
            status=TaskStatus.TODO
        )
        self.task2 = Task.objects.create(
            title="Refactor Ingestion Pipeline",
            assigned_to=self.user,
            created_by=self.user,
            priority=7,
            deadline=now + datetime.timedelta(days=2),
            status=TaskStatus.TODO
        )

    # -------------------------------------------------------------
    # 1. Fast Path Deterministic Commands
    # -------------------------------------------------------------
    def test_fast_path_timer_start_and_stop(self):
        r1 = NLPCommandService.parse_and_execute("start timer", self.user)
        self.assertTrue(r1['success'])
        self.assertIn("Timer started", r1['message'])

        r2 = NLPCommandService.parse_and_execute("stop timer", self.user)
        self.assertTrue(r2['success'])
        self.assertIn("Timer stopped", r2['message'])

    def test_fast_path_show_tasks(self):
        r = NLPCommandService.parse_and_execute("show my tasks", self.user)
        self.assertTrue(r['success'])
        self.assertIn("Refactor Query Pipeline", r['message'])

    def test_fast_path_schedule(self):
        r = NLPCommandService.parse_and_execute("show schedule", self.user)
        self.assertTrue(r['success'])

    def test_fast_path_productivity_summary(self):
        r = NLPCommandService.parse_and_execute("productivity summary", self.user)
        self.assertTrue(r['success'])

    def test_fast_path_ai_plan_day(self):
        r = NLPCommandService.parse_and_execute("plan my day", self.user)
        self.assertTrue(r['success'])

    def test_fast_path_free_slots(self):
        r = NLPCommandService.parse_and_execute("free slots", self.user)
        self.assertTrue(r['success'])
        self.assertIn("unallocated focus time", r['message'])

    def test_fast_path_help(self):
        r = NLPCommandService.parse_and_execute("help", self.user)
        self.assertTrue(r['success'])
        self.assertIn("I can assist you with", r['message'])

    def test_fast_path_reminders_list(self):
        r = NLPCommandService.parse_and_execute("show reminders", self.user)
        self.assertTrue(r['success'])

    def test_fast_path_notifications_list(self):
        r = NLPCommandService.parse_and_execute("show notifications", self.user)
        self.assertTrue(r['success'])

    # -------------------------------------------------------------
    # 2. Typo-Tolerant Queries
    # -------------------------------------------------------------
    def test_typo_remain_me(self):
        r = NLPCommandService.parse_and_execute("remain me 20 minuts before meeting", self.user)
        self.assertTrue(r['success'])
        self.assertIn("20 minutes", r['message'])

    def test_typo_scheudle(self):
        r = NLPCommandService.parse_and_execute("scheudle focus session tomorrow at 2pm", self.user)
        self.assertTrue(r['success'])
        self.assertEqual(r['canonical_action'], 'SCHEDULE_CREATE')

    def test_typo_complete_task(self):
        r = NLPCommandService.parse_and_execute(f"compelte task #{self.task1.id}", self.user)
        self.assertTrue(r['success'])
        self.task1.refresh_from_db()
        self.assertEqual(self.task1.status, TaskStatus.COMPLETED)

    # -------------------------------------------------------------
    # 3. Entity Rich Task Creation
    # -------------------------------------------------------------
    def test_create_task_with_entities(self):
        cmd = "create task called Setup Redis Cache tomorrow with priority 9"
        r = NLPCommandService.parse_and_execute(cmd, self.user)
        self.assertTrue(r['success'])
        self.assertEqual(r['canonical_action'], 'TASK_CREATE')
        self.assertIn("Setup Redis Cache", r['message'])

        created = Task.objects.filter(title="Setup Redis Cache").first()
        self.assertIsNotNone(created)
        self.assertEqual(created.priority, 9)

    # -------------------------------------------------------------
    # 4. Multi-turn Confirmation Flow (Destructive Action)
    # -------------------------------------------------------------
    def test_destructive_task_delete_with_confirmation(self):
        cid = "conv_test_delete_1"
        target_id = self.task2.id

        # Turn 1: Delete task -> Should require safety confirmation
        r1 = NLPCommandService.parse_and_execute(f"delete task #{target_id}", self.user, conversation_id=cid)
        self.assertTrue(r1['success'])
        self.assertTrue(r1['requires_confirmation'])
        self.assertIsNotNone(r1['preview'])

        # Task should NOT be deleted yet!
        self.assertTrue(Task.objects.filter(id=target_id).exists())

        # Turn 2: User says "yes" to confirm
        r2 = NLPCommandService.parse_and_execute("yes", self.user, conversation_id=cid)
        self.assertTrue(r2['success'])
        self.assertIn("Confirmed", r2['message'])

        # Now task IS deleted
        self.assertFalse(Task.objects.filter(id=target_id).exists())

    # -------------------------------------------------------------
    # 5. Multi-turn Cancellation Flow
    # -------------------------------------------------------------
    def test_destructive_task_delete_cancelled(self):
        cid = "conv_test_cancel_1"
        target_id = self.task1.id

        # Turn 1: Delete task -> Requires confirmation
        r1 = NLPCommandService.parse_and_execute(f"delete task #{target_id}", self.user, conversation_id=cid)
        self.assertTrue(r1['requires_confirmation'])

        # Turn 2: User cancels
        r2 = NLPCommandService.parse_and_execute("no", self.user, conversation_id=cid)
        self.assertTrue(r2['success'])
        self.assertIn("Action cancelled", r2['message'])

        # Task remains untouched
        self.assertTrue(Task.objects.filter(id=target_id).exists())

    # -------------------------------------------------------------
    # 6. Multi-turn Ambiguous Disambiguation Flow
    # -------------------------------------------------------------
    def test_ambiguous_task_disambiguation_flow(self):
        cid = "conv_test_ambig_1"

        # Turn 1: Complete "Refactor" (matches 2 tasks)
        r1 = NLPCommandService.parse_and_execute("complete task Refactor", self.user, conversation_id=cid)
        self.assertTrue(r1['success'])
        self.assertTrue(len(r1['candidates']) >= 2)
        self.assertIn("multiple matching tasks", r1['message'])

        # Turn 2: User picks candidate #1
        r2 = NLPCommandService.parse_and_execute("the first one", self.user, conversation_id=cid)
        self.assertTrue(r2['success'])
        self.task1.refresh_from_db()
        self.assertEqual(self.task1.status, TaskStatus.COMPLETED)

    # -------------------------------------------------------------
    # 7. AI & Analytics Queries
    # -------------------------------------------------------------
    def test_ai_recommendations(self):
        r = NLPCommandService.parse_and_execute("what should i work on", self.user)
        self.assertTrue(r['success'])

    def test_anomaly_check(self):
        r = NLPCommandService.parse_and_execute("check anomalies", self.user)
        self.assertTrue(r['success'])

    def test_productivity_trend(self):
        r = NLPCommandService.parse_and_execute("productivity trend", self.user)
        self.assertTrue(r['success'])
