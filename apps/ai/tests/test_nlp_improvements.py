import datetime
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.tasks.models import Task, TaskStatus
from apps.scheduling.models import ScheduleEvent, ScheduleEventType
from apps.tracking.models import TimeEntry, TimeEntryStatus
from apps.ai.services.nlp.service import NLPCommandService
from apps.ai.services.nlp.parser import NLPParser
from apps.ai.services.nlp.context import ContextManager


class NLPImprovementsTestCase(TestCase):
    """
    Focused verification tests for the 12 natural-language test cases
    specified in the user requirements, including multi-turn context,
    pronoun resolution, friendly responses, and grounded analytics.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email='assistant_user@example.com',
            username='assistant_user',
            password='testpassword123',
            timezone='Asia/Kolkata'
        )
        self.conv_id = "test_conv_nlp_improvements"

    # 1. "remind me tomorrow at 10pm to submit assignment"
    def test_remind_tomorrow_at_10pm(self):
        r = NLPCommandService.parse_and_execute(
            "remind me tomorrow at 10pm to submit assignment",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r['success'])
        self.assertEqual(r['canonical_action'], 'REMINDER_CREATE')
        self.assertIn("submit assignment", r['message'].lower())
        self.assertIn("10:00 pm", r['message'].lower())

    # 2. "remind me in 30 minutes to check database"
    def test_remind_in_30_minutes(self):
        r = NLPCommandService.parse_and_execute(
            "remind me in 30 minutes to check database",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r['success'])
        self.assertEqual(r['canonical_action'], 'REMINDER_CREATE')
        self.assertIn("30 minutes", r['message'])
        self.assertIn("check database", r['message'].lower())

    # 3. "schedule Python for tomorrow morning"
    def test_schedule_tomorrow_morning(self):
        r = NLPCommandService.parse_and_execute(
            "schedule Python for tomorrow morning",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r['success'])
        self.assertEqual(r['canonical_action'], 'SCHEDULE_CREATE')
        self.assertIn("Python", r['message'])
        event = ScheduleEvent.objects.filter(user=self.user, title__icontains="Python").first()
        self.assertIsNotNone(event)

    # 4. "create a Django task tomorrow at 5pm"
    def test_create_django_task(self):
        r = NLPCommandService.parse_and_execute(
            "create a Django task tomorrow at 5pm",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r['success'])
        self.assertEqual(r['canonical_action'], 'TASK_CREATE')
        self.assertIn("Django", r['message'])
        task = Task.objects.filter(assigned_to=self.user, title__icontains="Django").first()
        self.assertIsNotNone(task)

    # 5. "start my timer"
    def test_start_timer(self):
        r = NLPCommandService.parse_and_execute(
            "start my timer",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r['success'])
        self.assertEqual(r['canonical_action'], 'TIMER_START')
        self.assertIn("Timer started", r['message'])

    # 6. "stop it"
    def test_stop_it(self):
        # First ensure timer is started
        NLPCommandService.parse_and_execute("start my timer", self.user, conversation_id=self.conv_id)
        # Then stop it with pronoun "it"
        r = NLPCommandService.parse_and_execute(
            "stop it",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r['success'])
        self.assertEqual(r['canonical_action'], 'TIMER_STOP')
        self.assertIn("Timer stopped", r['message'])

    # 7. "how productive was I today?"
    def test_how_productive_was_i_today(self):
        r = NLPCommandService.parse_and_execute(
            "how productive was I today?",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r['success'])
        self.assertEqual(r['canonical_action'], 'PRODUCTIVITY_SUMMARY')
        # Grounded zero-hallucination check
        self.assertIn("productivity", r['message'].lower())

    # 8. "show my tasks tomorrow"
    def test_show_my_tasks_tomorrow(self):
        # Create a task due tomorrow
        tomorrow = timezone.now() + datetime.timedelta(days=1)
        Task.objects.create(
            title="Backend Architecture Review",
            assigned_to=self.user,
            created_by=self.user,
            deadline=tomorrow
        )
        r = NLPCommandService.parse_and_execute(
            "show my tasks tomorrow",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r['success'])
        self.assertIn("Backend Architecture Review", r['message'])

    # 9. "move it to Friday" (pronoun resolution to existing event with safety confirmation)
    def test_move_it_to_friday(self):
        event = ScheduleEvent.objects.create(
            user=self.user,
            title="Sprint Planning",
            start_at=timezone.now() + datetime.timedelta(days=1),
            end_at=timezone.now() + datetime.timedelta(days=1, hours=1),
            event_type=ScheduleEventType.MEETING
        )
        # Update context to set last event
        ContextManager.update_context(
            user_id=self.user.id,
            conversation_id=self.conv_id,
            last_event_id=event.id,
            last_event_title=event.title
        )

        # Turn 1: Request rescheduling
        r1 = NLPCommandService.parse_and_execute(
            "move it to Friday",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r1['success'])
        self.assertTrue(r1['requires_confirmation'])
        self.assertIn("Sprint Planning", r1['preview']['title'])

        # Turn 2: Confirm
        r2 = NLPCommandService.parse_and_execute(
            "yes",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r2['success'])
        self.assertIn("Sprint Planning", r2['message'])

    # 10. "make it 6pm instead"
    def test_make_it_6pm_instead(self):
        event = ScheduleEvent.objects.create(
            user=self.user,
            title="Client Sync",
            start_at=timezone.now() + datetime.timedelta(days=2),
            end_at=timezone.now() + datetime.timedelta(days=2, hours=1),
            event_type=ScheduleEventType.MEETING
        )
        ContextManager.update_context(
            user_id=self.user.id,
            conversation_id=self.conv_id,
            last_event_id=event.id,
            last_event_title=event.title
        )

        # Turn 1: Reschedule request stages confirmation
        r1 = NLPCommandService.parse_and_execute(
            "make it 6pm instead",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r1['success'])
        self.assertTrue(r1['requires_confirmation'])
        self.assertIn("Client Sync", r1['preview']['title'])

        # Turn 2: User confirms
        r2 = NLPCommandService.parse_and_execute(
            "yes",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r2['success'])
        self.assertIn("Client Sync", r2['message'])
        event.refresh_from_db()
        self.assertEqual(event.start_at.hour, 18)

    # 11. "remind me half an hour before my meeting"
    def test_remind_half_hour_before_meeting(self):
        # Create an upcoming meeting
        ScheduleEvent.objects.create(
            user=self.user,
            title="Weekly Team Meeting",
            start_at=timezone.now() + datetime.timedelta(hours=2),
            end_at=timezone.now() + datetime.timedelta(hours=3),
            event_type=ScheduleEventType.MEETING
        )
        r = NLPCommandService.parse_and_execute(
            "remind me half an hour before my meeting",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r['success'])
        self.assertEqual(r['canonical_action'], 'REMINDER_CREATE')
        self.assertIn("30 minutes", r['message'])

    # 12. "complete my Python task"
    def test_complete_my_python_task_single(self):
        py_task = Task.objects.create(
            title="Write Python unit tests",
            assigned_to=self.user,
            created_by=self.user,
            deadline=timezone.now() + datetime.timedelta(days=2),
            status=TaskStatus.TODO
        )
        r = NLPCommandService.parse_and_execute(
            "complete my Python task",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertTrue(r['success'])
        self.assertEqual(r['canonical_action'], 'TASK_COMPLETE')
        self.assertIn("completed", r['message'].lower())
        py_task.refresh_from_db()
        self.assertEqual(py_task.status, TaskStatus.COMPLETED)

    # Disambiguation: "complete my Python task" when MULTIPLE exist
    def test_complete_my_python_task_ambiguous(self):
        Task.objects.create(
            title="Python backend refactor",
            assigned_to=self.user,
            created_by=self.user,
            deadline=timezone.now() + datetime.timedelta(days=2),
            status=TaskStatus.TODO
        )
        Task.objects.create(
            title="Python script optimization",
            assigned_to=self.user,
            created_by=self.user,
            deadline=timezone.now() + datetime.timedelta(days=2),
            status=TaskStatus.TODO
        )
        r = NLPCommandService.parse_and_execute(
            "complete my Python task",
            self.user,
            conversation_id="disambig_test_conv"
        )
        self.assertTrue(r['success'])
        self.assertTrue(len(r['candidates']) >= 2)
        self.assertIn("multiple matching tasks", r['message'])
        self.assertIn("Which one do you mean?", r['message'])

    # Friendly Not Found response
    def test_friendly_not_found_response(self):
        r = NLPCommandService.parse_and_execute(
            "complete task NonexistentGhostTask",
            self.user,
            conversation_id=self.conv_id
        )
        self.assertFalse(r['success'])
        self.assertIn("I couldn't find task", r['message'])
        self.assertIn("Want me to search for similar tasks?", r['message'])

    # Multi-turn context preservation
    def test_multiturn_context_flow(self):
        cid = "multiturn_flow_test"
        # Turn 1: Create a Django task
        r1 = NLPCommandService.parse_and_execute("create task Django Feature", self.user, conversation_id=cid)
        self.assertTrue(r1['success'])
        session = ContextManager.get_session(self.user.id, cid)
        self.assertIsNotNone(session.last_task_id)
        self.assertEqual(session.last_task_title, "Django Feature")

        # Turn 2: Move it to Friday (staged for confirmation)
        r2 = NLPCommandService.parse_and_execute("move it to Friday", self.user, conversation_id=cid)
        self.assertTrue(r2['success'])
        self.assertTrue(r2['requires_confirmation'])
        self.assertIn("Django Feature", r2['preview']['title'])

        # Turn 3: User confirms
        r3 = NLPCommandService.parse_and_execute("yes", self.user, conversation_id=cid)
        self.assertTrue(r3['success'])
        self.assertIn("Django Feature", r3['message'])
