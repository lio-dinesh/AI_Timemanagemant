import datetime
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.ai.services.nlp.date_time import DateTimeNormalizer
from apps.ai.services.nlp.entities import EntityExtractor


class NLPEntitiesTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='entities_user@example.com', username='entities_user', password='pwd')

    def test_date_normalization(self):
        today = timezone.localdate()
        tomorrow = today + datetime.timedelta(days=1)

        _, d_today = DateTimeNormalizer.normalize_date("schedule for today", self.user)
        self.assertEqual(d_today, today.isoformat())

        _, d_tomorrow = DateTimeNormalizer.normalize_date("meeting tomorrow morning", self.user)
        self.assertEqual(d_tomorrow, tomorrow.isoformat())

    def test_time_normalization(self):
        t1, win1 = DateTimeNormalizer.normalize_time("meet at 10am", self.user)
        self.assertIsNotNone(t1)
        self.assertEqual(t1.hour, 10)
        self.assertEqual(t1.minute, 0)

        t2, win2 = DateTimeNormalizer.normalize_time("focus session at 2:30pm", self.user)
        self.assertIsNotNone(t2)
        self.assertEqual(t2.hour, 14)
        self.assertEqual(t2.minute, 30)

        _, win_morning = DateTimeNormalizer.normalize_time("in the morning", self.user)
        self.assertEqual(win_morning, "MORNING")

        _, win_afternoon = DateTimeNormalizer.normalize_time("tomorrow afternoon", self.user)
        self.assertEqual(win_afternoon, "AFTERNOON")

    def test_duration_normalization(self):
        d1 = DateTimeNormalizer.normalize_duration("work for 45 minutes")
        self.assertEqual(d1, 45)

        d2 = DateTimeNormalizer.normalize_duration("focus session for 2 hours")
        self.assertEqual(d2, 120)

    def test_period_normalization(self):
        p_week = DateTimeNormalizer.normalize_period("my report this week")
        self.assertEqual(p_week, "THIS_WEEK")

        p_last = DateTimeNormalizer.normalize_period("summary of last week")
        self.assertEqual(p_last, "LAST_WEEK")

        p_month = DateTimeNormalizer.normalize_period("productivity this month")
        self.assertEqual(p_month, "THIS_MONTH")

    def test_entity_extractor_full(self):
        text = "create task called Setup Redis Cache tomorrow at 10am with priority 8"
        entities = EntityExtractor.extract_entities(text, self.user)

        self.assertEqual(entities.task_title, "Setup Redis Cache")
        self.assertEqual(entities.priority, 8)
        self.assertIsNotNone(entities.date)
        self.assertEqual(entities.start_time, "10:00")

    def test_task_id_extraction(self):
        entities = EntityExtractor.extract_entities("complete task #14", self.user)
        self.assertEqual(entities.task_id, 14)

        entities2 = EntityExtractor.extract_entities("delete task 42", self.user)
        self.assertEqual(entities2.task_id, 42)

    def test_priority_keyword_mapping(self):
        urgent = EntityExtractor.extract_entities("create task Fix Production Bug urgent", self.user)
        self.assertEqual(urgent.priority, 9)

        low = EntityExtractor.extract_entities("create task Clean Docs low priority", self.user)
        self.assertEqual(low.priority, 2)
