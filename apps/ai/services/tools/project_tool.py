import datetime
from django.utils import timezone
from apps.projects.models import Project, ProjectStatus
from apps.ai.schemas import EntitySchema, ExecutionResultSchema
from apps.audit.services.auditor import AuditService


class ProjectTool:
    @staticmethod
    def create_project(user, entities: EntitySchema) -> ExecutionResultSchema:
        if not (user.is_manager_role or user.is_admin_role):
            return ExecutionResultSchema(
                success=False,
                action="PROJECT_CREATE",
                intent="PROJECT_CREATE",
                message="Permission Denied: Only Managers and Admins can create projects."
            )

        name = entities.project_title or "New Project"
        priority = entities.priority or 5
        now = timezone.now()

        if entities.date:
            try:
                d = datetime.date.fromisoformat(entities.date)
                deadline = timezone.make_aware(datetime.datetime.combine(d, datetime.time(18, 0)))
            except Exception:
                deadline = now + datetime.timedelta(days=14)
        else:
            deadline = now + datetime.timedelta(days=14)

        project = Project.objects.create(
            owner=user,
            name=name,
            priority=priority,
            deadline=deadline,
            status=ProjectStatus.ACTIVE
        )

        AuditService.log(
            action='PROJECT_CREATED',
            user=user,
            resource_type='Project',
            resource_id=project.id,
            status='SUCCESS',
            metadata={'name': name, 'source': 'NLP'}
        )

        return ExecutionResultSchema(
            success=True,
            action="PROJECT_CREATE",
            intent="PROJECT_CREATE",
            message=f"Created project '{project.name}' (deadline: {deadline.strftime('%b %d, %Y')}).",
            data={"project_id": project.id, "name": project.name},
            audit_logged=True
        )

    @staticmethod
    def search_projects(user, entities: EntitySchema) -> ExecutionResultSchema:
        qs = Project.objects.filter(owner=user)
        if entities.project_title:
            qs = qs.filter(name__icontains=entities.project_title)

        projects = list(qs.order_by('deadline', '-priority')[:5])
        if not projects:
            return ExecutionResultSchema(
                success=True,
                action="PROJECT_SEARCH",
                intent="PROJECT_SEARCH",
                message="No projects found.",
                data={"projects": []}
            )

        items = [f"'{p.name}' ({p.status}, due {p.deadline.strftime('%b %d')})" for p in projects]
        return ExecutionResultSchema(
            success=True,
            action="PROJECT_SEARCH",
            intent="PROJECT_SEARCH",
            message=f"Found {len(projects)} project(s): {', '.join(items)}.",
            data={"projects": [{"id": p.id, "name": p.name} for p in projects]}
        )

    @staticmethod
    def update_project(user, entities: EntitySchema) -> ExecutionResultSchema:
        p = Project.objects.filter(id=entities.project_id, owner=user).first() if entities.project_id else None
        if not p:
            return ExecutionResultSchema(
                success=False,
                action="PROJECT_UPDATE",
                intent="PROJECT_UPDATE",
                message="Target project not found to update."
            )
        if entities.date:
            d = datetime.date.fromisoformat(entities.date)
            p.deadline = timezone.make_aware(datetime.datetime.combine(d, datetime.time(18, 0)))
            p.save(update_fields=['deadline', 'updated_at'])
            return ExecutionResultSchema(
                success=True,
                action="PROJECT_UPDATE",
                intent="PROJECT_UPDATE",
                message=f"Updated project '{p.name}' deadline to {d.strftime('%b %d')}."
            )
        return ExecutionResultSchema(
            success=True,
            action="PROJECT_UPDATE",
            intent="PROJECT_UPDATE",
            message=f"Project '{p.name}' reviewed."
        )
