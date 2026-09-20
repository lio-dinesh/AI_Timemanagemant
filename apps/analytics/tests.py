from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.tracking.models import TimeEntry, TimeEntryStatus, ProductivityCategory
from apps.analytics.models import ProductivityDaily
from apps.analytics.services.aggregator import ProductivityAggregator

class AnalyticsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='analytics@example.com', username='analytics', password='pwd')
        self.today = timezone.localdate()

    def test_productivity_daily_aggregation_and_uniqueness(self):
        # Create a productive time entry
        start = timezone.make_aware(timezone.datetime.combine(self.today, timezone.datetime.min.time().replace(hour=10)))
        TimeEntry.objects.create(
            user=self.user,
            started_at=start,
            ended_at=start + timedelta(hours=2),
            duration_seconds=7200,
            active_seconds=7000,
            idle_seconds=200,
            status=TimeEntryStatus.CLOSED,
            productivity_category=ProductivityCategory.PRODUCTIVE
        )

        record = ProductivityAggregator.aggregate_user_date(self.user.id, self.today)
        self.assertEqual(record.tracked_seconds, 7200)
        self.assertEqual(record.productive_seconds, 7200)
        self.assertEqual(record.productivity_score, 100.0)

        # Assert unique row per user per date
        self.assertEqual(ProductivityDaily.objects.filter(user=self.user, date=self.today).count(), 1)

    def test_user_dashboard_render_with_ai_recommendations(self):
        from apps.ai.models import AIInsight, InsightType, InsightStatus
        AIInsight.objects.create(
            user=self.user,
            insight_type=InsightType.PERSONALIZED_RECOMMENDATION,
            status=InsightStatus.ACTIVE,
            confidence=0.85,
            payload={
                "type": "DEEP_WORK_BLOCK",
                "title": "Optimal 50-Minute Focus Sprint",
                "action_suggestion": "Your schedule is clear between 10:00 AM and 11:30 AM. Perfect slot for deep coding or strategic planning."
            }
        )
        self.client.force_login(self.user)
        response = self.client.get('/analytics/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Optimal 50-Minute Focus Sprint")
        self.assertContains(response, "Your schedule is clear between 10:00 AM and 11:30 AM.")

