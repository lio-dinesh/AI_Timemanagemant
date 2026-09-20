from typing import Tuple, List, Optional, Dict, Any
from django.db.models import Q
from apps.tasks.models import Task, TaskStatus
from apps.projects.models import Project
from apps.scheduling.models import ScheduleEvent
from apps.ai.schemas import EntitySchema, ContextSessionSchema
from .context import ContextManager


class ResolutionError(Exception):
    pass


class EntityResolver:
    @staticmethod
    def resolve_task(
        user,
        entities: EntitySchema,
        session: Optional[ContextSessionSchema] = None
    ) -> Tuple[Optional[Task], List[Dict[str, Any]], float]:
        """
        Resolves a single Task object or returns a list of ambiguous candidate dictionaries.
        Returns: (resolved_task, candidates_list, confidence_score)
        """
        # 1. Direct ID resolution
        if entities.task_id:
            task = Task.objects.filter(id=entities.task_id, assigned_to=user).first()
            if not task and user.is_manager_role:
                sub_ids = list(user.subordinates.values_list('id', flat=True))
                task = Task.objects.filter(id=entities.task_id, assigned_to_id__in=sub_ids).first()
            if task:
                return task, [], 1.0
            return None, [], 0.0

        # 2. Context resolution: check if user previously had candidate list and is picking by title/keyword
        if session and session.candidate_entities:
            query = (entities.task_title or entities.raw_text if hasattr(entities, 'raw_text') else "")
            if not query and entities.extra.get('raw_text'):
                query = entities.extra.get('raw_text')

            if query:
                q_lower = query.lower()
                matched_candidates = []
                for cand in session.candidate_entities:
                    if (q_lower in cand['title'].lower() or
                        ("api" in q_lower and "api" in cand['title'].lower()) or
                        ("dsa" in q_lower and "dsa" in cand['title'].lower()) or
                        ("ml" in q_lower and "ml" in cand['title'].lower())):
                        matched_candidates.append(cand)

                if len(matched_candidates) == 1:
                    resolved = Task.objects.filter(id=matched_candidates[0]['id']).first()
                    if resolved:
                        return resolved, [], 0.95

        # 3. Search by task_title keyword
        if entities.task_title:
            qs = Task.objects.filter(assigned_to=user).filter(
                Q(title__icontains=entities.task_title) |
                Q(description__icontains=entities.task_title)
            )

            count = qs.count()
            if count == 1:
                return qs.first(), [], 0.95
            elif count > 1:
                # Ambiguous! Return candidates for user clarification
                candidates = [
                    {
                        "id": t.id,
                        "title": t.title,
                        "priority": t.priority,
                        "status": t.status,
                        "deadline": t.deadline.strftime("%Y-%m-%d %H:%M") if t.deadline else None
                    }
                    for t in qs[:5]
                ]
                return None, candidates, 0.60

        # 4. Fallback: next active/in-progress task
        active_task = Task.objects.filter(
            assigned_to=user,
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ).order_by('-priority', 'deadline').first()

        if active_task:
            return active_task, [], 0.70

        return None, [], 0.0

    @staticmethod
    def resolve_project(
        user,
        entities: EntitySchema
    ) -> Tuple[Optional[Project], List[Dict[str, Any]], float]:
        """Resolves a Project object or candidate list."""
        if entities.project_id:
            p = Project.objects.filter(id=entities.project_id, owner=user).first()
            if p:
                return p, [], 1.0

        if entities.project_title:
            qs = Project.objects.filter(owner=user, name__icontains=entities.project_title)
            count = qs.count()
            if count == 1:
                return qs.first(), [], 0.95
            elif count > 1:
                candidates = [{"id": p.id, "title": p.name, "status": p.status} for p in qs[:5]]
                return None, candidates, 0.60

        return None, [], 0.0
