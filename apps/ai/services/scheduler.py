import datetime
from django.utils import timezone
from apps.tasks.models import Task, TaskStatus
from apps.scheduling.models import ScheduleEvent, ScheduleEventType, ScheduleEventStatus
from apps.scheduling.services.scheduler import ScheduleService
from apps.ai.models import AIInsight, InsightType, InsightStatus

class SchedulingOptimizer:
    @staticmethod
    def optimize_schedule_for_user(user, target_date=None):
        """
        AI optimizer that finds open slots in user's work hours,
        prioritizes high-priority impending tasks, and creates AIInsight proposals.
        """
        if not target_date:
            target_date = timezone.localdate() + datetime.timedelta(days=1)

        # 1. Parse user's work hours
        work_start = user.work_start_time or datetime.time(9, 0)
        work_end = user.work_end_time or datetime.time(17, 0)

        day_start = timezone.make_aware(datetime.datetime.combine(target_date, work_start))
        day_end = timezone.make_aware(datetime.datetime.combine(target_date, work_end))

        # 2. Existing events during the target day
        existing_events = list(ScheduleService.get_user_schedule(user, day_start, day_end))

        # 3. High priority active tasks assigned to user
        candidate_tasks = list(Task.objects.filter(
            assigned_to=user,
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ).order_by('-priority', 'deadline'))

        if not candidate_tasks:
            return []

        # Find open slots
        slots = []
        curr_pointer = day_start
        for ev in existing_events:
            if ev.start_at > curr_pointer:
                # Slot between curr_pointer and ev.start_at
                duration_mins = int((ev.start_at - curr_pointer).total_seconds() / 60)
                if duration_mins >= 30:
                    slots.append((curr_pointer, ev.start_at, duration_mins))
            curr_pointer = max(curr_pointer, ev.end_at)

        if curr_pointer < day_end:
            duration_mins = int((day_end - curr_pointer).total_seconds() / 60)
            if duration_mins >= 30:
                slots.append((curr_pointer, day_end, duration_mins))

        insights_created = []
        for i, task in enumerate(candidate_tasks[:len(slots)]):
            slot_start, slot_end, slot_mins = slots[i]
            # Duration recommended: either 60 mins or available slot
            alloc_mins = min(slot_mins, max(30, task.estimated_seconds // 60 or 60))
            rec_end = slot_start + datetime.timedelta(minutes=alloc_mins)

            payload = {
                "task_id": task.id,
                "task_title": task.title,
                "recommended_start": slot_start.isoformat(),
                "recommended_end": rec_end.isoformat(),
                "duration_minutes": alloc_mins,
                "reason": f"Optimal focus window matching priority {task.priority} before deadline {task.deadline.strftime('%Y-%m-%d')}",
            }

            insight = AIInsight.objects.create(
                user=user,
                task=task,
                insight_type=InsightType.SCHEDULE_RECOMMENDATION,
                status=InsightStatus.ACTIVE,
                confidence=0.91,
                model_name="ConstraintOptimizer_v1",
                payload=payload,
                expires_at=day_end
            )
            insights_created.append(insight)

        return insights_created

    @staticmethod
    def apply_schedule_recommendation(insight_id, user):
        """
        Deterministic backend validation before creating actual schedule event.
        """
        insight = AIInsight.objects.get(id=insight_id, user=user)
        if insight.status != InsightStatus.ACTIVE:
            raise ValueError("Insight is not active or already applied.")

        payload = insight.payload
        start_at = datetime.datetime.fromisoformat(payload['recommended_start'])
        end_at = datetime.datetime.fromisoformat(payload['recommended_end'])

        # Deterministic conflict check
        conflicts = ScheduleService.detect_conflicts(user, start_at, end_at)
        if conflicts:
            raise ValueError("Conflict detected with existing calendar block. Schedule cannot be applied.")

        event = ScheduleService.create_event(
            user=user,
            title=f"[AI] {payload.get('task_title', 'Focus Session')}",
            start_at=start_at,
            end_at=end_at,
            event_type=ScheduleEventType.FOCUS,
            task_id=insight.task_id,
            source="AI",
            description=payload.get('reason', '')
        )

        insight.apply()
        return event
