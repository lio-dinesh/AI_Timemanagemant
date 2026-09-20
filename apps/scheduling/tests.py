from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.scheduling.services.scheduler import ScheduleService, ConflictError
from apps.scheduling.services.calendar_sync import CalendarSyncService

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

    def test_calendar_sync_ics_and_urls(self):
        start1 = self.now + timedelta(hours=2)
        end1 = start1 + timedelta(hours=1)
        ev = ScheduleService.create_event(
            self.user, "Sprint Review & Demo", start1, end1,
            description="Discuss AI scheduling milestones",
            location="Room 401 / Zoom"
        )

        # 1. Test .ics generator
        ics_text = CalendarSyncService.generate_ics_content([ev], calendar_name="Team Schedule")
        self.assertIn("BEGIN:VCALENDAR", ics_text)
        self.assertIn("BEGIN:VEVENT", ics_text)
        self.assertIn("SUMMARY:Sprint Review & Demo", ics_text)
        self.assertIn("LOCATION:Room 401 / Zoom", ics_text)
        self.assertIn("END:VCALENDAR", ics_text)

        # 2. Test Google & Outlook URL generators
        google_url = CalendarSyncService.get_google_calendar_url(ev)
        self.assertTrue(google_url.startswith("https://calendar.google.com/calendar/render?"))
        self.assertIn("Sprint+Review", google_url)

        outlook_url = CalendarSyncService.get_outlook_calendar_url(ev)
        self.assertTrue(outlook_url.startswith("https://outlook.live.com/calendar/0/deeplink/compose?"))
        self.assertIn("Sprint+Review", outlook_url)
