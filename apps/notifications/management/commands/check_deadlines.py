from django.core.management.base import BaseCommand
from apps.notifications.services.engine import NotificationEngine


class Command(BaseCommand):
    help = 'Scans for tasks due in 24h, 1h, overdue tasks, and upcoming meetings, dispatching in-app and email notifications.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting deadline and reminder scan..."))
        count = NotificationEngine.scan_and_generate_reminders()
        self.stdout.write(self.style.SUCCESS(f"Successfully dispatched {count} reminder/deadline notifications."))
