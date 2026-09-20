from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.tasks.models import Task, TaskStatus
from apps.ai.models import AIInsight, InsightType, InsightStatus
from apps.ai.services.scheduler import SchedulingOptimizer
from apps.ai.services.nlp import NLPCommandService


class AITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='ai_user@example.com', username='ai_user', password='pwd')
        self.task = Task.objects.create(
            title="Database Optimization",
            assigned_to=self.user,
            created_by=self.user,
            priority=8,
            estimated_seconds=3600,
            deadline=timezone.now() + timedelta(days=2)
        )

    def test_scheduling_optimizer_creates_insight_proposals(self):
        insights = SchedulingOptimizer.optimize_schedule_for_user(self.user)
        self.assertGreaterEqual(len(insights), 1)
        ins = insights[0]
        self.assertEqual(ins.insight_type, InsightType.SCHEDULE_RECOMMENDATION)
        self.assertEqual(ins.status, InsightStatus.ACTIVE)
        self.assertIn("recommended_start", ins.payload)

    def test_apply_insight_creates_calendar_event(self):
        insights = SchedulingOptimizer.optimize_schedule_for_user(self.user)
        ins = insights[0]
        event = SchedulingOptimizer.apply_schedule_recommendation(ins.id, self.user)
        self.assertIsNotNone(event.id)
        ins.refresh_from_db()
        self.assertEqual(ins.status, InsightStatus.APPLIED)

    def test_nlp_command_understanding_and_execution(self):
        result = NLPCommandService.parse_and_execute("Schedule my task tomorrow morning", self.user)
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'SCHEDULE')

    def test_nlp_reminder_with_typo_tolerance(self):
        result = NLPCommandService.parse_and_execute("remain me 30 minutes before meeting", self.user)
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'REMINDER')
        self.assertIn("30 minutes", result['message'])

        result2 = NLPCommandService.parse_and_execute("remind me 15 minutes before demo", self.user)
        self.assertTrue(result2['success'])
        self.assertEqual(result2['action'], 'REMINDER')
        self.assertIn("15 minutes", result2['message'])

    def test_nlp_timer_controls(self):
        res_start = NLPCommandService.parse_and_execute("start timer", self.user)
        self.assertTrue(res_start['success'])
        self.assertEqual(res_start['action'], 'TIMER')

        res_stop = NLPCommandService.parse_and_execute("stop timer", self.user)
        self.assertTrue(res_stop['success'])
        self.assertEqual(res_stop['action'], 'TIMER')

    def test_ai_insight_display_text_and_title(self):
        ins1 = AIInsight.objects.create(
            user=self.user,
            insight_type=InsightType.PERSONALIZED_RECOMMENDATION,
            status=InsightStatus.ACTIVE,
            payload={
                "type": "DEEP_WORK_BLOCK",
                "title": "Optimal 50-Minute Focus Sprint",
                "action_suggestion": "Your schedule is clear between 10:00 AM and 11:30 AM."
            }
        )
        self.assertEqual(ins1.title, "Optimal 50-Minute Focus Sprint")
        self.assertEqual(ins1.display_text, "Your schedule is clear between 10:00 AM and 11:30 AM.")
        self.assertEqual(ins1.summary, ins1.display_text)

        ins2 = AIInsight.objects.create(
            user=self.user,
            insight_type=InsightType.SCHEDULE_RECOMMENDATION,
            payload={"reason": "Optimal window"}
        )
        self.assertEqual(ins2.display_text, "Optimal window")

        ins3 = AIInsight.objects.create(
            user=self.user,
            insight_type=InsightType.ANOMALY,
            payload={"suggestion": "Long running timer"}
        )
        self.assertEqual(ins3.display_text, "Long running timer")

    def test_insights_dashboard_render_with_various_payloads(self):
        AIInsight.objects.create(
            user=self.user,
            insight_type=InsightType.PERSONALIZED_RECOMMENDATION,
            status=InsightStatus.ACTIVE,
            confidence=0.85,
            payload={
                "type": "DEEP_WORK_BLOCK",
                "title": "Optimal 50-Minute Focus Sprint",
                "action_suggestion": "Your schedule is clear between 10:00 AM and 11:30 AM."
            }
        )
        self.client.force_login(self.user)
        from django.urls import reverse
        response = self.client.get(reverse('ai_insights'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Optimal 50-Minute Focus Sprint")
        self.assertContains(response, "Your schedule is clear between 10:00 AM and 11:30 AM.")
