import uuid
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.tasks.models import Task, TaskStatus
from apps.tracking.models import (
    TimeEntry, TimeEntryStatus, TimeEntrySource, TrackingMethod, ProductivityCategory
)
from apps.tracking.services.classifier import ProductivityClassifier
from apps.tasks.services.task import TaskService
from apps.audit.services.auditor import AuditService

class TimerConflictError(Exception):
    pass

class TimerNotFoundError(Exception):
    pass


class TimerService:
    @staticmethod
    def start_timer(user, task_id=None, activity_type="General Work", source=TimeEntrySource.MANUAL, method=TrackingMethod.TIMER, notes=None, app_name=None, domain_name=None, request=None):
        """
        Starts an authoritative server-side timer for the user.
        Transactionally locks user record to prevent concurrent active timers.
        """
        with transaction.atomic():
            # Lock the user row to serialize concurrent timer start requests
            locked_user = User.objects.select_for_update().get(id=user.id)

            # Assert no OPEN timer currently exists
            existing_open = TimeEntry.objects.filter(
                user=locked_user,
                status=TimeEntryStatus.OPEN
            ).first()

            if existing_open:
                raise TimerConflictError(f"An active timer (session {existing_open.session_uuid}) is already running. Please stop it first.")

            task = None
            project = None
            if task_id:
                try:
                    task = Task.objects.select_related('project').get(id=task_id)
                    project = task.project
                    # Automatically update task to IN_PROGRESS if TODO
                    if task.status == TaskStatus.TODO:
                        task.status = TaskStatus.IN_PROGRESS
                        if not task.started_at:
                            task.started_at = timezone.now()
                        task.save(update_fields=['status', 'started_at', 'updated_at'])
                except Task.DoesNotExist:
                    raise ValueError("Specified task does not exist.")

            # Classify productivity
            cat, conf = ProductivityClassifier.classify(activity_type, app_name or "", domain_name or "")

            entry = TimeEntry.objects.create(
                user=locked_user,
                task=task,
                project=project,
                session_uuid=uuid.uuid4(),
                started_at=timezone.now(),
                status=TimeEntryStatus.OPEN,
                source=source,
                tracking_method=method,
                activity_type=activity_type,
                application_name=app_name,
                domain_name=domain_name,
                productivity_category=cat,
                classification_confidence=conf,
                notes=notes or ""
            )

            AuditService.log(
                action='TIME_STARTED',
                user=locked_user,
                resource_type='TimeEntry',
                resource_id=entry.id,
                request=request,
                status='SUCCESS',
                metadata={'task_id': task_id, 'session_uuid': str(entry.session_uuid)}
            )

            return entry

    @staticmethod
    def stop_timer(user, session_uuid=None, idle_seconds=0, notes=None, request=None):
        """
        Stops active timer, calculates server-side duration, closes entry,
        updates task actual_seconds, and enqueues daily productivity recalculation.
        """
        with transaction.atomic():
            qs = TimeEntry.objects.select_for_update().filter(
                user=user,
                status=TimeEntryStatus.OPEN
            )
            if session_uuid:
                qs = qs.filter(session_uuid=session_uuid)

            entry = qs.first()
            if not entry:
                raise TimerNotFoundError("No active open timer found to stop.")

            now = timezone.now()
            duration = max(1, int((now - entry.started_at).total_seconds()))
            safe_idle = min(max(0, int(idle_seconds)), duration)
            active_seconds = duration - safe_idle

            entry.ended_at = now
            entry.duration_seconds = duration
            entry.idle_seconds = safe_idle
            entry.active_seconds = active_seconds
            entry.status = TimeEntryStatus.CLOSED
            if notes:
                entry.notes = f"{entry.notes}\n{notes}".strip() if entry.notes else notes
            entry.save()

            # Update cached actual_seconds on Task
            if entry.task_id:
                TaskService.recalculate_task_actual_seconds(entry.task_id)

            # Queue asynchronous daily productivity aggregation
            try:
                from apps.analytics.tasks import calculate_daily_productivity
                calculate_daily_productivity.delay(user.id, entry.started_at.strftime('%Y-%m-%d'))
            except Exception:
                # If Celery worker is offline, synchronous fallback or eager execution handles it
                pass

            AuditService.log(
                action='TIME_STOPPED',
                user=user,
                resource_type='TimeEntry',
                resource_id=entry.id,
                request=request,
                status='SUCCESS',
                metadata={
                    'session_uuid': str(entry.session_uuid),
                    'duration_seconds': duration,
                    'idle_seconds': safe_idle
                }
            )

            return entry

    @staticmethod
    def create_manual_entry(user, start_time, end_time, task_id=None, activity_type="Work", category=ProductivityCategory.PRODUCTIVE, notes=None, idle_seconds=0, request=None):
        """
        Creates a closed manual time entry with server-side validation.
        """
        if end_time <= start_time:
            raise ValueError("End time must be strictly after start time.")

        duration = int((end_time - start_time).total_seconds())
        safe_idle = min(max(0, int(idle_seconds)), duration)
        active_seconds = duration - safe_idle

        task = None
        project = None
        if task_id:
            task = Task.objects.select_related('project').get(id=task_id)
            project = task.project

        with transaction.atomic():
            entry = TimeEntry.objects.create(
                user=user,
                task=task,
                project=project,
                session_uuid=uuid.uuid4(),
                started_at=start_time,
                ended_at=end_time,
                duration_seconds=duration,
                idle_seconds=safe_idle,
                active_seconds=active_seconds,
                status=TimeEntryStatus.CLOSED,
                source=TimeEntrySource.MANUAL,
                tracking_method=TrackingMethod.TIMER,
                activity_type=activity_type,
                productivity_category=category,
                notes=notes or ""
            )

            if task:
                TaskService.recalculate_task_actual_seconds(task.id)

            try:
                from apps.analytics.tasks import calculate_daily_productivity
                calculate_daily_productivity.delay(user.id, start_time.strftime('%Y-%m-%d'))
            except Exception:
                pass

            return entry

    @staticmethod
    def get_active_timer(user):
        return TimeEntry.objects.filter(user=user, status=TimeEntryStatus.OPEN).select_related('task', 'project').first()
