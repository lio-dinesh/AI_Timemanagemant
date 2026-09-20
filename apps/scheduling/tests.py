from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.scheduling.services.scheduler import ScheduleService, ConflictError

class SchedulingTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='sched@example.com', username='sched', password='pwd')
        self.now = timezone.now()

    def test_detect_conflict_and_prevent_overlap(self):
        # Create initial event 10:00 - 11:00
        start1 = self.now + timedelta(hours=1)
        end1 = start1 + timedelta(hours=1)
        ScheduleService.create_event(self.user, "Existing Meeting", start1, end1)

        # Attempt overlapping event 10:30 - 11:30
        start2 = start1 + timedelta(minutes=30)
        end2 = start2 + timedelta(hours=1)

        with self.assertRaises(ConflictError):
            ScheduleService.create_event(self.user, "Conflicting Meeting", start2, end2)

    def test_non_overlapping_event_succeeds(self):
        start1 = self.now + timedelta(hours=1)
        end1 = start1 + timedelta(hours=1)
        ScheduleService.create_event(self.user, "Meeting A", start1, end1)

        # Later event 11:15 - 12:00
        start2 = end1 + timedelta(minutes=15)
        end2 = start2 + timedelta(minutes=45)
        ev2 = ScheduleService.create_event(self.user, "Meeting B", start2, end2)
        self.assertIsNotNone(ev2.id)
