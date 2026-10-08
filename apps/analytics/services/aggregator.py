import datetime
from django.db.models import Sum, Count, Q
from django.utils import timezone
from apps.accounts.models import User
from apps.tracking.models import TimeEntry, TimeEntryStatus, ProductivityCategory
from apps.scheduling.models import ScheduleEvent, ScheduleEventType, ScheduleEventStatus
from apps.tasks.models import Task, TaskStatus
from apps.analytics.models import ProductivityDaily

class ProductivityAggregator:
    @staticmethod
    def aggregate_user_date(user_id, target_date):
        """
        Recalculates or creates a single ProductivityDaily aggregate row for (user_id, target_date).
        Never scans all historical data—only records for this specific 24-hour day.
        """
        if isinstance(target_date, str):
            target_date = datetime.datetime.strptime(target_date, '%Y-%m-%d').date()

        day_start = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time.min))
        day_end = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time.max))

        # 1. Aggregate Time Entries
        entries_agg = TimeEntry.objects.filter(
            user_id=user_id,
            started_at__range=(day_start, day_end),
            status=TimeEntryStatus.CLOSED
        ).aggregate(
            total_duration=Sum('duration_seconds'),
            total_active=Sum('active_seconds'),
            total_idle=Sum('idle_seconds'),
            productive=Sum('duration_seconds', filter=Q(productivity_category=ProductivityCategory.PRODUCTIVE)),
            nonproductive=Sum('duration_seconds', filter=Q(productivity_category=ProductivityCategory.DISTRACTION)),
            neutral=Sum('duration_seconds', filter=Q(productivity_category=ProductivityCategory.NEUTRAL)),
        )

        tracked_seconds = entries_agg['total_duration'] or 0
        active_seconds = entries_agg['total_active'] or 0
        idle_seconds = entries_agg['total_idle'] or 0
        productive_seconds = entries_agg['productive'] or 0
        nonproductive_seconds = entries_agg['nonproductive'] or 0
        neutral_seconds = entries_agg['neutral'] or 0

        # 2. Aggregate Schedule Events
        events = ScheduleEvent.objects.filter(
            user_id=user_id,
            start_at__range=(day_start, day_end)
        ).exclude(status=ScheduleEventStatus.CANCELLED)

        meeting_seconds = 0
        focus_seconds = 0
        break_seconds = 0
        scheduled_seconds = 0

        for ev in events:
            ev_sec = max(0, int((ev.end_at - ev.start_at).total_seconds()))
            scheduled_seconds += ev_sec
            if ev.event_type == ScheduleEventType.MEETING:
                meeting_seconds += ev_sec
            elif ev.event_type == ScheduleEventType.FOCUS:
                focus_seconds += ev_sec
            elif ev.event_type == ScheduleEventType.BREAK:
                break_seconds += ev_sec

        # 3. Aggregate Tasks for User based on target_date (tasks given or assigned to user)
        all_user_tasks = list(Task.objects.filter(Q(assigned_to_id=user_id) | Q(created_by_id=user_id)).distinct())
        today = timezone.localdate()
        is_today = (target_date == today)

        if is_today:
            # On today: evaluate all currently active and assigned tasks for the user
            relevant_tasks = all_user_tasks
            tasks_total = len(relevant_tasks)
            tasks_completed = len([t for t in relevant_tasks if t.status == TaskStatus.COMPLETED])
            tasks_overdue = len([t for t in relevant_tasks if t.deadline and t.deadline < timezone.now() and t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)])

            # Work completed or updated today
            task_actual_today = sum(t.actual_seconds for t in relevant_tasks if t.updated_at and t.updated_at.date() == today)
            task_completed_today = sum(t.estimated_seconds for t in relevant_tasks if t.completed_at and t.completed_at.date() == today)
            today_task_work = max(task_actual_today, task_completed_today)

            if tracked_seconds == 0 and today_task_work > 0:
                tracked_seconds = today_task_work
                productive_seconds = today_task_work
        else:
            # On historical past days: ONLY evaluate tasks that were actually completed, had deadlines, or created on that specific target_date
            relevant_tasks = [
                t for t in all_user_tasks
                if (t.completed_at and t.completed_at.date() == target_date)
                or (t.deadline and t.deadline.date() == target_date)
                or (t.created_at and t.created_at.date() == target_date)
            ]
            tasks_total = len(relevant_tasks)
            tasks_completed = len([t for t in relevant_tasks if t.status == TaskStatus.COMPLETED and t.completed_at and t.completed_at.date() == target_date])
            tasks_overdue = len([t for t in relevant_tasks if t.deadline and t.deadline.date() == target_date and t.deadline < day_end and t.status != TaskStatus.COMPLETED])

            # Historical task work credited only if tasks were completed on that date
            task_completed_work = sum(t.estimated_seconds for t in relevant_tasks if t.status == TaskStatus.COMPLETED and t.completed_at and t.completed_at.date() == target_date)
            if tracked_seconds == 0 and task_completed_work > 0:
                tracked_seconds = task_completed_work
                productive_seconds = task_completed_work

        # 4. Computed Scores
        if tasks_total > 0:
            completion_rate = round((tasks_completed / tasks_total) * 100, 2)
            avg_progress = round(sum(t.progress for t in relevant_tasks) / tasks_total, 2)
            on_time_bonus = max(0, 15 - (tasks_overdue * 2))
            task_score = min(100.0, round((completion_rate * 0.60) + (avg_progress * 0.25) + on_time_bonus, 2))
        else:
            completion_rate = 100.0 if tasks_completed > 0 else 0.0
            task_score = 0.0

        timer_score = round((productive_seconds / max(tracked_seconds, 1) * 100), 2) if entries_agg['total_duration'] else 0.0

        if entries_agg['total_duration'] and tasks_total > 0:
            productivity_score = round(0.5 * timer_score + 0.5 * task_score, 2)
        elif entries_agg['total_duration']:
            productivity_score = timer_score
        elif tasks_total > 0:
            productivity_score = task_score
        else:
            productivity_score = 0.0

        focus_rate = round(((focus_seconds + productive_seconds) / max(tracked_seconds, 1) * 100), 2) if tracked_seconds > 0 else 0.0

        # Harmonic efficiency score
        if completion_rate > 0 and productivity_score > 0:
            efficiency_score = round(2 * (completion_rate * productivity_score) / (completion_rate + productivity_score), 2)
        else:
            efficiency_score = round((completion_rate + productivity_score) / 2, 2)

        # 5. Peak focus window heuristic
        peak_start = None
        peak_end = None
        if productive_seconds > 0:
            # Check morning vs afternoon
            morning_prod = TimeEntry.objects.filter(
                user_id=user_id,
                started_at__range=(day_start, day_start + datetime.timedelta(hours=13)),
                productivity_category=ProductivityCategory.PRODUCTIVE,
                status=TimeEntryStatus.CLOSED
            ).aggregate(s=Sum('duration_seconds'))['s'] or 0

            afternoon_prod = productive_seconds - morning_prod
            if morning_prod >= afternoon_prod:
                peak_start = datetime.time(9, 30)
                peak_end = datetime.time(11, 30)
            else:
                peak_start = datetime.time(14, 0)
                peak_end = datetime.time(16, 0)

        # 6. Update or Create row
        daily_record, _ = ProductivityDaily.objects.update_or_create(
            user_id=user_id,
            date=target_date,
            defaults={
                'productive_seconds': productive_seconds,
                'nonproductive_seconds': nonproductive_seconds,
                'neutral_seconds': neutral_seconds,
                'tracked_seconds': tracked_seconds,
                'active_seconds': active_seconds,
                'idle_seconds': idle_seconds,
                'focus_seconds': focus_seconds,
                'meeting_seconds': meeting_seconds,
                'break_seconds': break_seconds,
                'tasks_total': tasks_total,
                'tasks_completed': tasks_completed,
                'tasks_overdue': tasks_overdue,
                'scheduled_seconds': scheduled_seconds,
                'completion_rate': min(100.0, completion_rate),
                'focus_rate': min(100.0, focus_rate),
                'productivity_score': min(100.0, productivity_score),
                'efficiency_score': min(100.0, efficiency_score),
                'peak_start_time': peak_start,
                'peak_end_time': peak_end,
                'generated_at': timezone.now()
            }
        )

        return daily_record
