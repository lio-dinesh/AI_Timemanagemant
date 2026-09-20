import time
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.tracking.models import TimeEntry, TimeEntryStatus
from apps.tracking.services.timer import TimerService, TimerConflictError, TimerNotFoundError

class TrackingTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='tracker@example.com', username='tracker', password='pwd')

    def test_start_timer_success(self):
        entry = TimerService.start_timer(user=self.user, activity_type="Django Coding")
        self.assertEqual(entry.status, TimeEntryStatus.OPEN)
        self.assertIsNotNone(entry.session_uuid)
        self.assertEqual(entry.user, self.user)

    def test_prevent_duplicate_active_timer(self):
        TimerService.start_timer(user=self.user, activity_type="Session 1")
        with self.assertRaises(TimerConflictError):
            TimerService.start_timer(user=self.user, activity_type="Session 2")

    def test_stop_timer_calculates_server_duration(self):
        open_entry = TimerService.start_timer(user=self.user)
        # Modify started_at to simulate a 30-minute session
        TimeEntry.objects.filter(id=open_entry.id).update(started_at=timezone.now() - timedelta(minutes=30))

        closed_entry = TimerService.stop_timer(user=self.user, idle_seconds=120)
        self.assertEqual(closed_entry.status, TimeEntryStatus.CLOSED)
        self.assertGreaterEqual(closed_entry.duration_seconds, 1799)
        self.assertEqual(closed_entry.idle_seconds, 120)
        self.assertEqual(closed_entry.active_seconds, closed_entry.duration_seconds - 120)

    def test_manual_entry_validation(self):
        now = timezone.now()
        # Invalid: end time before start time
        with self.assertRaises(ValueError):
            TimerService.create_manual_entry(
                user=self.user,
                start_time=now,
                end_time=now - timedelta(hours=1)
            )

        # Valid entry
        entry = TimerService.create_manual_entry(
            user=self.user,
            start_time=now - timedelta(hours=1),
            end_time=now
        )
        self.assertEqual(entry.duration_seconds, 3600)
        self.assertEqual(entry.status, TimeEntryStatus.CLOSED)
