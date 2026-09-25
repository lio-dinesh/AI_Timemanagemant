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
            else:
                # Explicit title provided, but 0 matches found. Do NOT guess!
                return None, [], 0.0

        # 4. Context pronoun resolution (e.g. "move it", "complete it")
        if session and session.last_task_id:
            last_t = Task.objects.filter(id=session.last_task_id, assigned_to=user).first()
            if last_t:
                return last_t, [], 0.90

        # 5. Fallback: only if user gave no title or ID at all
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

    @staticmethod
    def resolve_user(reference: Optional[str], current_user) -> Optional[Any]:
        """
        Resolves a User by email, username, full name, or contextual reference ("me", "myself").
        """
        if not reference:
            return current_user

        ref_clean = reference.strip()
        ref_lower = ref_clean.lower()

        if ref_lower in ("me", "myself", "self", "i"):
            return current_user

        from apps.accounts.models import User

        # 1. Direct email match (e.g. liodinesh1905@gmail.com)
        user_by_email = User.objects.filter(email__iexact=ref_clean).first()
        if user_by_email:
            return user_by_email

        # 2. Direct username match (e.g. admin, dinesh)
        user_by_uname = User.objects.filter(username__iexact=ref_clean).first()
        if user_by_uname:
            return user_by_uname

        # 3. Partial email match (e.g. liodinesh)
        user_by_email_prefix = User.objects.filter(email__icontains=ref_clean).first()
        if user_by_email_prefix:
            return user_by_email_prefix

        # 4. First name or Last name match (e.g. Dinesh, Dinesh G)
        user_by_name = User.objects.filter(
            Q(first_name__icontains=ref_clean) |
            Q(last_name__icontains=ref_clean) |
            Q(username__icontains=ref_clean)
        ).first()
        if user_by_name:
            return user_by_name

        # 5. Extract email if embedded in string
        import re
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', ref_clean)
        if email_match:
            found = User.objects.filter(email__iexact=email_match.group(0)).first()
            if found:
                return found

        return None
