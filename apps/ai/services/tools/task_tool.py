import datetime
from django.utils import timezone
from apps.tasks.models import Task, TaskStatus
from apps.accounts.models import User
from apps.ai.schemas import EntitySchema, ExecutionResultSchema
from apps.audit.services.auditor import AuditService
from apps.notifications.services.engine import NotificationEngine
from apps.ai.services.nlp.resolver import EntityResolver


class TaskTool:
    @staticmethod
    def create_task(user, entities: EntitySchema) -> ExecutionResultSchema:
        title = entities.task_title or "Untitled Task"
        priority = entities.priority or 5
        description = entities.extra.get('description', '')

        # Resolve assignee (support assigning to others via NLP e.g. liodinesh1905@gmail.com, Dinesh)
        assigned_user = EntityResolver.resolve_user(entities.user_reference, user) or user

        # Calculate deadline
        now = timezone.now()
        if entities.date:
            try:
                d = datetime.date.fromisoformat(entities.date)
                hour = 18
                minute = 0
                if entities.start_time:
                    parts = entities.start_time.split(":")
                    hour = int(parts[0])
                    minute = int(parts[1]) if len(parts) > 1 else 0
                deadline = timezone.make_aware(datetime.datetime.combine(d, datetime.time(hour, minute)))
            except Exception:
                deadline = now + datetime.timedelta(days=1)
        else:
            deadline = now + datetime.timedelta(days=1)

        task = Task.objects.create(
            title=title,
            description=description,
            assigned_to=assigned_user,
            created_by=user,
            priority=priority,
            deadline=deadline,
            status=TaskStatus.TODO,
            category=entities.category or "WORK"
        )

        AuditService.log(
            action='TASK_CREATED',
            user=user,
            resource_type='Task',
            resource_id=task.id,
            status='SUCCESS',
            metadata={'title': title, 'priority': priority, 'assigned_to': assigned_user.email, 'source': 'NLP'}
        )

        # Dispatch In-App & Email notification to assignee
        NotificationEngine.notify_task_assigned(task, assigned_by=user)
        from apps.analytics.services.aggregator import ProductivityAggregator
        ProductivityAggregator.aggregate_user_date(task.assigned_to_id, timezone.localdate())

        assignee_display = assigned_user.get_full_name() or assigned_user.username
        assignee_str = f" assigned to {assignee_display}" if assigned_user.id != user.id else ""
        notif_str = f" Notification sent to {assigned_user.email}." if assigned_user.email and assigned_user.id != user.id else ""

        return ExecutionResultSchema(
            success=True,
            action="TASK_CREATE",
            intent="TASK_CREATE",
            message=f"Done — I've created the {task.title} task with priority {task.priority}{assignee_str} (due {deadline.strftime('%b %d, %Y at %I:%M %p')}).{notif_str}",
            data={
                "task_id": task.id,
                "title": task.title,
                "priority": task.priority,
                "assigned_to": assigned_user.email,
                "deadline": deadline.isoformat()
            },
            audit_logged=True
        )

    @staticmethod
    def complete_task(user, entities: EntitySchema, resolved_task: Task = None) -> ExecutionResultSchema:
        task = resolved_task
        if not task and entities.task_id:
            task = Task.objects.filter(id=entities.task_id, assigned_to=user).first()

        if not task:
            return ExecutionResultSchema(
                success=False,
                action="TASK_COMPLETE",
                intent="TASK_COMPLETE",
                message="I couldn't find that task. Want me to search for similar tasks?"
            )

        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.completed_at = timezone.now()
        task.save(update_fields=['status', 'progress', 'completed_at', 'updated_at'])

        AuditService.log(
            action='TASK_COMPLETED',
            user=user,
            resource_type='Task',
            resource_id=task.id,
            status='SUCCESS',
            metadata={'title': task.title, 'source': 'NLP'}
        )

        # Dispatch In-App & Email notification to creator/assignee
        NotificationEngine.notify_task_completed(task, completed_by=user)
        from apps.analytics.services.aggregator import ProductivityAggregator
        ProductivityAggregator.aggregate_user_date(task.assigned_to_id, timezone.localdate())

        return ExecutionResultSchema(
            success=True,
            action="TASK_COMPLETE",
            intent="TASK_COMPLETE",
            message=f"Marked task '{task.title}' as COMPLETED. Done! I've marked your task as completed.",
            data={"task_id": task.id, "title": task.title, "status": task.status},
            audit_logged=True
        )

    @staticmethod
    def update_task(user, entities: EntitySchema, resolved_task: Task = None) -> ExecutionResultSchema:
        task = resolved_task
        if not task and entities.task_id:
            task = Task.objects.filter(id=entities.task_id, assigned_to=user).first()

        if not task:
            return ExecutionResultSchema(
                success=False,
                action="TASK_UPDATE",
                intent="TASK_UPDATE",
                message="I couldn't find that task. Want me to search for similar tasks?"
            )

        updates = []
        if entities.priority:
            task.priority = entities.priority
            updates.append(f"priority to {entities.priority}")
        if entities.date:
            try:
                d = datetime.date.fromisoformat(entities.date)
                hour = 18
                minute = 0
                if entities.start_time:
                    parts = entities.start_time.split(":")
                    hour = int(parts[0])
                    minute = int(parts[1]) if len(parts) > 1 else 0
                task.deadline = timezone.make_aware(datetime.datetime.combine(d, datetime.time(hour, minute)))
                updates.append(f"deadline to {task.deadline.strftime('%A, %b %d at %I:%M %p')}")
            except Exception:
                pass
        elif entities.start_time and task.deadline:
            try:
                parts = entities.start_time.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                target_date = timezone.localdate(task.deadline)
                task.deadline = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time(hour, minute)))
                updates.append(f"time to {task.deadline.strftime('%I:%M %p')}")
            except Exception:
                pass

        if not updates:
            updates.append("details updated")

        task.save(update_fields=['priority', 'deadline', 'updated_at'])

        return ExecutionResultSchema(
            success=True,
            action="TASK_UPDATE",
            intent="TASK_UPDATE",
            message=f"Updated task '{task.title}': {', '.join(updates)}.",
            data={"task_id": task.id, "title": task.title}
        )

    @staticmethod
    def delete_task(user, entities: EntitySchema, resolved_task: Task = None) -> ExecutionResultSchema:
        task = resolved_task
        if not task and entities.task_id:
            task = Task.objects.filter(id=entities.task_id, assigned_to=user).first()

        if not task:
            return ExecutionResultSchema(
                success=False,
                action="TASK_DELETE",
                intent="TASK_DELETE",
                message="Could not find the specified task to delete."
            )

        task_id = task.id
        task_title = task.title
        task.delete()

        AuditService.log(
            action='TASK_DELETED',
            user=user,
            resource_type='Task',
            resource_id=task_id,
            status='SUCCESS',
            metadata={'title': task_title, 'source': 'NLP'}
        )

        return ExecutionResultSchema(
            success=True,
            action="TASK_DELETE",
            intent="TASK_DELETE",
            message=f"Deleted task '{task_title}'.",
            data={"task_id": task_id, "title": task_title},
            audit_logged=True
        )

    @staticmethod
    def search_tasks(user, entities: EntitySchema) -> ExecutionResultSchema:
        now = timezone.now()
        qs = Task.objects.filter(assigned_to=user)

        if entities.date:
            try:
                target_d = datetime.date.fromisoformat(entities.date)
                qs = qs.filter(deadline__date=target_d)
                label = f"due on {target_d.strftime('%A, %b %d')}"
            except Exception:
                pass
        elif entities.extra.get('overdue') or "overdue" in (entities.extra.get('raw_text') or ""):
            qs = qs.filter(deadline__lt=now, status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS])
            label = "overdue"
        elif entities.task_title:
            qs = qs.filter(title__icontains=entities.task_title)
            label = f"matching '{entities.task_title}'"
        else:
            qs = qs.filter(status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS])
            label = "active"

        tasks = list(qs.order_by('deadline', '-priority')[:5])
        if not tasks:
            return ExecutionResultSchema(
                success=True,
                action="TASK_SEARCH",
                intent="TASK_SEARCH",
                message=f"No {label} tasks found.",
                data={"tasks": []}
            )

        items = [f"'{t.title}' (P{t.priority}, due {t.deadline.strftime('%b %d') if t.deadline else 'none'})" for t in tasks]
        return ExecutionResultSchema(
            success=True,
            action="TASK_SEARCH",
            intent="TASK_SEARCH",
            message=f"Found {len(tasks)} {label} task(s): {'; '.join(items)}.",
            data={"tasks": [{"id": t.id, "title": t.title, "priority": t.priority} for t in tasks]}
        )

    @staticmethod
    def analyze_tasks(user, entities: EntitySchema) -> ExecutionResultSchema:
        from apps.tasks.services.task import TaskService
        tasks = list(TaskService.get_user_tasks(user))
        total = len(tasks)

        if total == 0:
            return ExecutionResultSchema(
                success=True,
                action="TASK_ANALYZE",
                intent="TASK_ANALYZE",
                message="You don't have any tasks assigned yet. Add a task with 'Create task [title]' to start organizing your workload!",
                data={"total": 0}
            )

        now = timezone.now()
        completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]
        in_progress = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]
        todo = [t for t in tasks if t.status == TaskStatus.TODO]
        blocked = [t for t in tasks if t.status == TaskStatus.BLOCKED]
        overdue = [t for t in tasks if t.deadline and t.deadline < now and t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)]

        completed_count = len(completed)
        in_progress_count = len(in_progress)
        todo_count = len(todo)
        overdue_count = len(overdue)

        # Workload hours
        est_hours = round(sum(t.estimated_seconds for t in tasks) / 3600, 1)
        completed_hours = round(sum(t.estimated_seconds for t in completed) / 3600, 1)
        actual_hours = round(sum(t.actual_seconds for t in tasks) / 3600, 1)

        # Completion rate & performance score
        completion_rate = round((completed_count / total) * 100, 1)
        avg_progress = round(sum(t.progress for t in tasks) / total, 1) if total > 0 else 0.0

        # Calculate a realistic productivity / task health score
        on_time_bonus = max(0, 15 - (overdue_count * 2))
        task_score = min(100.0, round((completion_rate * 0.60) + (avg_progress * 0.25) + on_time_bonus, 1))

        # Top priority active tasks
        active_tasks = [t for t in tasks if t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)]
        active_tasks.sort(key=lambda x: (-x.priority, x.deadline or now))
        top_task = active_tasks[0] if active_tasks else None

        # Smart AI Strategic Breakdown via Google Gemini 3.6 Flash
        from apps.ai.services.llm_provider import get_llm_provider, GeminiLLMProvider
        provider = get_llm_provider()
        gemini_strategic_summary = None

        if isinstance(provider, GeminiLLMProvider) and total > 0:
            try:
                task_summaries = []
                for t in tasks[:15]:
                    d_str = t.deadline.strftime('%b %d') if t.deadline else 'no deadline'
                    is_ov = "⚠️ OVERDUE" if (t.deadline and t.deadline < now and t.status != TaskStatus.COMPLETED) else ""
                    task_summaries.append(
                        f"- '{t.title}' [Status: {t.status}, Priority: P{t.priority}, Due: {d_str}, Est: {round(t.estimated_seconds/3600, 1)}h, Logged: {round(t.actual_seconds/3600, 1)}h {is_ov}]"
                    )

                tasks_context = "\n".join(task_summaries)
                prompt = (
                    f"User has {total} tasks ({completed_count} completed, {in_progress_count} in-progress, {todo_count} to-do, {overdue_count} overdue).\n"
                    f"Total estimated workload: {est_hours}h. Total logged time: {actual_hours}h. Current task health score: {task_score}%.\n\n"
                    f"Task list:\n{tasks_context}\n\n"
                    "Provide an executive, high-impact AI productivity breakdown in 3 to 4 concise bullet points:\n"
                    "1. Executive Assessment (efficiency & workload balance)\n"
                    "2. Critical Risks or Bottlenecks (flag overdue or high-priority items)\n"
                    "3. Immediate Next Action (exact task to execute right now and why)\n"
                    "4. Smart Time-Saving Advice (concrete tactical optimization technique)\n"
                    "Format with bold keywords and bullet points. Be concise, actionable, and inspiring."
                )
                system_prompt = "You are an elite AI Executive Productivity Coach powered by Google Gemini 3.6 Flash."
                raw_gemini_resp = provider.complete(prompt, system=system_prompt)
                if raw_gemini_resp and len(raw_gemini_resp.strip()) > 40:
                    gemini_strategic_summary = raw_gemini_resp.strip()
            except Exception as e:
                logger.warning("Gemini task analysis exception: %s", e)

        if gemini_strategic_summary:
            parts = []
            parts.append(f"✨ **Google Gemini 3.6 Flash — Intelligent Task & Workload Analysis**")
            parts.append(f"📊 **Metrics**: **{completed_count}/{total}** Completed ({completion_rate}%) | Workload: **{est_hours}h** | Logged: **{actual_hours}h** | Health Score: **{task_score}%**")
            if overdue_count > 0:
                parts.append(f"⚠️ **Attention**: {overdue_count} task(s) currently overdue!")
            parts.append("")
            parts.append(gemini_strategic_summary)
            msg = "\n".join(parts)
        else:
            # Fallback to rich deterministic formatting
            parts = []
            parts.append(f"📊 **Workload & Task Analysis ({total} Total Tasks)**:")
            parts.append(f"• Completed: **{completed_count}** ({completion_rate}%) | In Progress: **{in_progress_count}** | To Do: **{todo_count}**")
            parts.append(f"• Estimated Workload: **{est_hours}h** | Logged Time: **{actual_hours}h** | Health Score: **{task_score}%**")

            if overdue_count > 0:
                top_overdue = sorted(overdue, key=lambda x: -x.priority)[0]
                parts.append(f"• ⚠️ **{overdue_count} Overdue Task(s)**! Urgent: *'{top_overdue.title}'* (Priority {top_overdue.priority}).")

            if top_task:
                due_str = f", due {top_task.deadline.strftime('%b %d')}" if top_task.deadline else ""
                parts.append(f"• 🎯 **Recommended Next Action**: Focus on *'{top_task.title}'* (Priority {top_task.priority}{due_str}).")
            elif completed_count == total:
                parts.append("• 🎉 **Outstanding!** All your tasks are completed. Ready for a well-deserved break or next sprint.")

            msg = "\n".join(parts)

        return ExecutionResultSchema(
            success=True,
            action="TASK_ANALYZE",
            intent="TASK_ANALYZE",
            message=msg,
            data={
                "total": total,
                "completed": completed_count,
                "in_progress": in_progress_count,
                "todo": todo_count,
                "overdue": overdue_count,
                "completion_rate": completion_rate,
                "task_score": task_score,
                "estimated_hours": est_hours,
                "logged_hours": actual_hours,
                "top_task_id": top_task.id if top_task else None
            }
        )

    @staticmethod
    def list_tasks(user, entities: EntitySchema) -> ExecutionResultSchema:
        return TaskTool.search_tasks(user, entities)

    @staticmethod
    def assign_task(user, entities: EntitySchema, resolved_task: Task = None) -> ExecutionResultSchema:
        if not (user.is_manager_role or user.is_admin_role):
            return ExecutionResultSchema(
                success=False,
                action="TASK_ASSIGN",
                intent="TASK_ASSIGN",
                message="Permission Denied: Only Managers and Admins can assign tasks."
            )

        task = resolved_task or (Task.objects.filter(id=entities.task_id).first() if entities.task_id else None)
        if not task:
            return ExecutionResultSchema(
                success=False,
                action="TASK_ASSIGN",
                intent="TASK_ASSIGN",
                message="Could not find the target task to assign."
            )

        assignee = EntityResolver.resolve_user(entities.user_reference, user)
        if not assignee:
            target_str = entities.user_reference or "specified user"
            return ExecutionResultSchema(
                success=False,
                action="TASK_ASSIGN",
                intent="TASK_ASSIGN",
                message=f"Could not find user '{target_str}' to assign task."
            )

        task.assigned_to = assignee
        task.save(update_fields=['assigned_to', 'updated_at'])

        # Dispatch In-App & Email notification to new assignee
        NotificationEngine.notify_task_assigned(task, assigned_by=user)

        assignee_name = assignee.get_full_name() or assignee.username
        notif_info = f" Email notification dispatched to {assignee.email}." if assignee.email else ""

        return ExecutionResultSchema(
            success=True,
            action="TASK_ASSIGN",
            intent="TASK_ASSIGN",
            message=f"Assigned task '{task.title}' to {assignee_name}.{notif_info}",
            data={"task_id": task.id, "assignee_id": assignee.id, "assignee_email": assignee.email}
        )

    @staticmethod
    def get_help(user, entities: EntitySchema) -> ExecutionResultSchema:
        return ExecutionResultSchema(
            success=True,
            action="HELP",
            intent="HELP",
            message=(
                "I can assist you with: "
                "1) Tasks: 'Create task Deploy API tomorrow', 'Complete Python task', 'Show overdue tasks' | "
                "2) Timer: 'Start timer', 'Stop timer' | "
                "3) Schedule: 'Schedule 2 hours for Python tomorrow morning', 'What is on my schedule today?' | "
                "4) Reminders: 'Remind me 30 minutes before meeting' | "
                "5) Analytics: 'How much time did I track today?', 'Show my most time-consuming task' | "
                "6) Reports: 'Email me my weekly report'."
            )
        )

    @staticmethod
    def unknown_command(user, entities: EntitySchema) -> ExecutionResultSchema:
        return ExecutionResultSchema(
            success=False,
            action="UNKNOWN",
            intent="UNKNOWN",
            message="Could not understand command. Try typing: 'Schedule task tomorrow morning', 'Start timer', or 'Show my tasks'."
        )
