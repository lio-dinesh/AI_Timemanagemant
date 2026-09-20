from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import User, UserRole
from apps.projects.models import Project, ProjectStatus
from apps.tasks.models import Task, TaskStatus
from apps.scheduling.models import ScheduleEvent, ScheduleEventType
from apps.notifications.services.engine import NotificationEngine
from apps.notifications.models import NotificationType, NotificationPriority
from apps.analytics.services.aggregator import ProductivityAggregator
from apps.tracking.services.timer import TimerService

class Command(BaseCommand):
    help = 'Seeds initial demonstration users, projects, and tasks'

    def handle(self, *args, **options):
        self.stdout.write("Seeding initial data...")

        # 1. Admin
        admin, created = User.objects.get_or_create(
            email='admin@aitime.com',
            defaults={
                'username': 'admin',
                'first_name': 'System',
                'last_name': 'Administrator',
                'role': UserRole.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin.set_password('Admin@123456')
            admin.save()
            self.stdout.write("Created Admin: admin@aitime.com / Admin@123456")

        # 2. Manager
        manager, created = User.objects.get_or_create(
            email='manager@aitime.com',
            defaults={
                'username': 'manager',
                'first_name': 'Sarah',
                'last_name': 'Connor',
                'role': UserRole.MANAGER,
                'manager': admin
            }
        )
        if created:
            manager.set_password('Manager@123456')
            manager.save()
            self.stdout.write("Created Manager: manager@aitime.com / Manager@123456")

        # 3. Employee
        employee, created = User.objects.get_or_create(
            email='employee@aitime.com',
            defaults={
                'username': 'employee',
                'first_name': 'John',
                'last_name': 'Doe',
                'role': UserRole.EMPLOYEE,
                'manager': manager
            }
        )
        if created:
            employee.set_password('Employee@123456')
            employee.save()
            self.stdout.write("Created Employee: employee@aitime.com / Employee@123456")

        # 4. Sample Project
        now = timezone.now()
        project, _ = Project.objects.get_or_create(
            name="AI Time Management Core Platform",
            owner=manager,
            defaults={
                'description': "Enterprise-ready AI time allocation and productivity optimization platform.",
                'status': ProjectStatus.ACTIVE,
                'priority': 9,
                'deadline': now + timedelta(days=30)
            }
        )

        # 5. Sample Tasks
        task1, _ = Task.objects.get_or_create(
            title="Implement Celery Reminder Scheduler",
            project=project,
            defaults={
                'description': "Configure Celery Beat periodic task for scanning 24h/1h deadline reminders.",
                'assigned_to': employee,
                'created_by': manager,
                'status': TaskStatus.IN_PROGRESS,
                'priority': 8,
                'progress': 40,
                'estimated_seconds': 7200,
                'deadline': now + timedelta(hours=22),
                'category': 'Backend'
            }
        )

        task2, _ = Task.objects.get_or_create(
            title="Design Executive Analytics Dashboard",
            project=project,
            defaults={
                'description': "Create Chart.js visual graphs for productivity trend and team metrics.",
                'assigned_to': employee,
                'created_by': manager,
                'status': TaskStatus.TODO,
                'priority': 9,
                'progress': 0,
                'estimated_seconds': 10800,
                'deadline': now + timedelta(days=3),
                'category': 'Frontend'
            }
        )

        # 6. Sample Schedule Event
        ScheduleEvent.objects.get_or_create(
            user=employee,
            title="Daily Engineering Standup",
            defaults={
                'event_type': ScheduleEventType.MEETING,
                'start_at': now + timedelta(hours=2),
                'end_at': now + timedelta(hours=2, minutes=30),
                'location': 'Virtual Google Meet',
                'meeting_url': 'https://meet.google.com/xyz-demo'
            }
        )

        # 7. Sample Initial Notifications
        NotificationEngine.create_notification(
            user=employee,
            title="Welcome to AI Time Management",
            message="Your account has been configured with AI scheduling and time tracking capabilities.",
            notification_type=NotificationType.TASK_ASSIGNED,
            priority=NotificationPriority.NORMAL
        )

        # 8. Seed sample historical closed time entries & calculate daily productivity
        yesterday = timezone.localdate() - timedelta(days=1)
        start_y = timezone.make_aware(timezone.datetime.combine(yesterday, timezone.datetime.min.time().replace(hour=9, minute=30)))
        end_y = start_y + timedelta(hours=3, minutes=15)

        TimerService.create_manual_entry(
            user=employee,
            start_time=start_y,
            end_time=end_y,
            task_id=task1.id,
            activity_type="Python/Django Backend Development",
            notes="Implemented core data pipeline and service models."
        )

        ProductivityAggregator.aggregate_user_date(employee.id, yesterday)
        ProductivityAggregator.aggregate_user_date(employee.id, timezone.localdate())

        self.stdout.write(self.style.SUCCESS("Initial demo dataset seeded successfully!"))
