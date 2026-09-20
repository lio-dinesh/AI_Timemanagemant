import datetime
from django.utils import timezone
from apps.tasks.models import Task, TaskStatus
from apps.accounts.models import User
from apps.ai.schemas import EntitySchema, ExecutionResultSchema
from apps.audit.services.auditor import AuditService


class TaskTool:
    @staticmethod
    def create_task(user, entities: EntitySchema) -> ExecutionResultSchema:
        title = entities.task_title or "Untitled Task"
        priority = entities.priority or 5

        # Calculate deadline
        now = timezone.now()
        if entities.date:
            try:
                d = datetime.date.fromisoformat(entities.date)
                deadline = timezone.make_aware(datetime.datetime.combine(d, datetime.time(18, 0)))
            except Exception:
                deadline = now + datetime.timedelta(days=1)
        else:
            deadline = now + datetime.timedelta(days=1)

        task = Task.objects.create(
            title=title,
            assigned_to=user,
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
            metadata={'title': title, 'priority': priority, 'source': 'NLP'}
        )

        return ExecutionResultSchema(
            success=True,
            action="TASK_CREATE",
            intent="TASK_CREATE",
            message=f"Created task '{task.title}' with priority {task.priority} (due {deadline.strftime('%b %d, %Y')}).",
            data={
                "task_id": task.id,
                "title": task.title,
                "priority": task.priority,
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
                message="Could not find the specified task to complete."
            )

        task.status = TaskStatus.COMPLETED
        task.completed_at = timezone.now()
        task.save(update_fields=['status', 'completed_at', 'updated_at'])

        AuditService.log(
            action='TASK_COMPLETED',
            user=user,
            resource_type='Task',
            resource_id=task.id,
            status='SUCCESS',
            metadata={'title': task.title, 'source': 'NLP'}
        )

        return ExecutionResultSchema(
            success=True,
            action="TASK_COMPLETE",
            intent="TASK_COMPLETE",
            message=f"Marked task '{task.title}' as COMPLETED.",
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
                message="Could not find the specified task to update."
            )

        updates = []
        if entities.priority:
            task.priority = entities.priority
            updates.append(f"priority to {entities.priority}")
        if entities.date:
            d = datetime.date.fromisoformat(entities.date)
            task.deadline = timezone.make_aware(datetime.datetime.combine(d, datetime.time(18, 0)))
            updates.append(f"deadline to {d.strftime('%b %d')}")

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

        if entities.extra.get('overdue') or "overdue" in (entities.extra.get('raw_text') or ""):
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

        target_username = entities.user_reference or ""
        assignee = User.objects.filter(username__icontains=target_username).first()
        if not assignee:
            return ExecutionResultSchema(
                success=False,
                action="TASK_ASSIGN",
                intent="TASK_ASSIGN",
                message=f"Could not find user '{target_username}' to assign task."
            )

        task.assigned_to = assignee
        task.save(update_fields=['assigned_to', 'updated_at'])

        return ExecutionResultSchema(
            success=True,
            action="TASK_ASSIGN",
            intent="TASK_ASSIGN",
            message=f"Assigned task '{task.title}' to {assignee.get_full_name() or assignee.username}.",
            data={"task_id": task.id, "assignee_id": assignee.id}
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
