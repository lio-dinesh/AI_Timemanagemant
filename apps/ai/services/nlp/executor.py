import uuid
import logging
from typing import Optional
from django.utils import timezone
from apps.tasks.models import Task
from apps.projects.models import Project
from apps.audit.services.auditor import AuditService
from apps.ai.schemas import (
    CommandSchema,
    ExecutionResultSchema,
    ActionPreviewSchema,
    EntitySchema,
)
from apps.ai.services.nlp.intents import (
    IntentType,
    get_intent_definition,
    RiskLevel,
)
from apps.ai.services.nlp.policy import PolicyEngine
from apps.ai.services.nlp.resolver import EntityResolver
from apps.ai.services.nlp.context import ContextManager
from apps.ai.services.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class NLPExecutor:
    """
    Authoritative NLP Command Execution Engine.
    Enforces security, policy validation, entity resolution, confirmation staging,
    and dispatches execution strictly through ToolRegistry.
    """

    @classmethod
    def execute(cls, command: CommandSchema, user) -> ExecutionResultSchema:
        user_id = user.id if hasattr(user, 'id') else 0

        # 1. Sliding-Window Rate Limit Enforcement
        is_heavy = command.intent in (IntentType.AI_SCHEDULE.value, IntentType.REPORT_GENERATE.value)
        rate_ok, rate_msg = PolicyEngine.check_rate_limit(user_id, is_heavy_ai=is_heavy)
        if not rate_ok:
            return ExecutionResultSchema(
                success=False,
                action=command.intent,
                intent=command.intent,
                message=rate_msg or "Rate limit exceeded."
            )

        # 2. Input Sanitization and Prompt Injection Defense
        safe, clean_text, sec_msg = PolicyEngine.sanitize_input(command.raw_text)
        if not safe:
            AuditService.log(
                action='SECURITY_VIOLATION',
                user=user,
                resource_type='NLPCommand',
                status='FAILED',
                metadata={'raw_text': command.raw_text, 'reason': sec_msg}
            )
            return ExecutionResultSchema(
                success=False,
                action=command.intent,
                intent=command.intent,
                message=f"Security Alert: {sec_msg}"
            )

        # 3. Handle Meta-Intents: CONFIRM, CANCEL, CANDIDATE_SELECT
        if command.intent == 'CONFIRM':
            return cls._handle_confirm(command, user)
        elif command.intent == 'CANCEL':
            return cls._handle_cancel(command, user)
        elif command.intent == 'CANDIDATE_SELECT':
            return cls._handle_candidate_select(command, user)

        # 4. RBAC, Ownership, and Role Authorization
        auth_ok, auth_err, intent_def = PolicyEngine.authorize_command(command, user)
        if not auth_ok:
            AuditService.log(
                action='RBAC_REJECTED',
                user=user,
                resource_type='NLPCommand',
                status='FAILED',
                metadata={'intent': command.intent, 'reason': auth_err}
            )
            return ExecutionResultSchema(
                success=False,
                action=command.intent,
                intent=command.intent,
                message=auth_err or "Action not authorized."
            )

        # 5. Entity Resolution
        session = ContextManager.get_session(user_id, command.conversation_id)
        resolved_entity = None

        if (intent_def.category == 'task' and command.intent != IntentType.TASK_CREATE.value) or command.intent in (
            IntentType.TIMER_START.value,
            IntentType.SCHEDULE_CREATE.value,
            IntentType.TIME_ENTRY_CREATE.value
        ):
            # Only resolve if title or ID is provided or required
            if command.entities.task_id or command.entities.task_title or command.intent in (
                IntentType.TASK_COMPLETE.value,
                IntentType.TASK_DELETE.value,
                IntentType.TASK_UPDATE.value,
                IntentType.TASK_ASSIGN.value
            ):
                resolved_entity, candidates, conf = EntityResolver.resolve_task(user, command.entities, session)
                if candidates:
                    ContextManager.update_context(
                        user_id=user_id,
                        conversation_id=command.conversation_id,
                        last_intent=command.intent,
                        candidate_entities=candidates,
                        pending_entities=command.entities.to_dict()
                    )
                    cand_lines = [
                        f"{i+1}. #{c['id']} {c['title']} (Priority {c.get('priority', '-')})"
                        for i, c in enumerate(candidates)
                    ]
                    return ExecutionResultSchema(
                        success=True,
                        action=command.intent,
                        intent=command.intent,
                        message=f"I found multiple matching tasks. Which one would you like?\n" + "\n".join(cand_lines),
                        candidates=candidates
                    )

                if not resolved_entity and command.intent in (
                    IntentType.TASK_COMPLETE.value,
                    IntentType.TASK_DELETE.value,
                    IntentType.TASK_UPDATE.value
                ):
                    target_name = command.entities.task_title or (f"#{command.entities.task_id}" if command.entities.task_id else "recent")
                    return ExecutionResultSchema(
                        success=False,
                        action=command.intent,
                        intent=command.intent,
                        message=f"Could not find active task '{target_name}' to {command.intent.lower().replace('_', ' ')}."
                    )

        # 6. Confirmation Staging (for Destructive or Explicit Confirmation intents)
        if intent_def.requires_confirmation or command.requires_confirmation:
            token = str(uuid.uuid4())[:8]
            target_name = resolved_entity.title if resolved_entity else (command.entities.task_title or intent_def.category.title())
            diff = {
                "intent": command.intent,
                "entities": command.entities.to_dict(),
                "target_id": resolved_entity.id if resolved_entity else None,
                "target_name": target_name
            }
            preview = ActionPreviewSchema(
                action_type=command.intent,
                title=f"Confirm: {command.intent} '{target_name}'",
                description=f"Are you sure you want to execute {command.intent.lower().replace('_', ' ')} on '{target_name}'?",
                diff_summary=diff,
                confirm_token=token,
                expires_at=(timezone.now() + timezone.timedelta(minutes=10)).isoformat()
            )
            ContextManager.set_pending_confirmation(user_id, preview)
            ContextManager.update_context(
                user_id=user_id,
                conversation_id=command.conversation_id,
                last_intent=command.intent,
                pending_action=command.intent,
                pending_entities=command.entities.to_dict(),
                confirmation_token=token
            )
            return ExecutionResultSchema(
                success=True,
                action=command.intent,
                intent=command.intent,
                requires_confirmation=True,
                preview=preview,
                message=f"Safety Confirmation: Are you sure you want to {command.intent.lower().replace('_', ' ')} '{target_name}'? (Reply 'yes' to proceed or 'no' to cancel)"
            )

        # 7. Execute Controlled Tool via ToolRegistry
        try:
            itype = IntentType(command.intent)
        except ValueError:
            itype = IntentType.UNKNOWN

        result = ToolRegistry.execute(itype, user, command.entities, resolved_entity)

        # 8. Update Multi-turn Context Session
        ContextManager.update_context(
            user_id=user_id,
            conversation_id=command.conversation_id,
            last_intent=command.intent,
            pending_entities=command.entities.to_dict()
        )

        return result

    @classmethod
    def _handle_confirm(cls, command: CommandSchema, user) -> ExecutionResultSchema:
        user_id = user.id if hasattr(user, 'id') else 0
        session = ContextManager.get_session(user_id, command.conversation_id)
        token = command.confirmation_token or (session.confirmation_token if session else None)

        if not token:
            return ExecutionResultSchema(
                success=False,
                action="CONFIRM",
                intent="CONFIRM",
                message="There is no pending action waiting for confirmation."
            )

        pending_data = ContextManager.get_pending_confirmation(user_id, token)
        if not pending_data:
            return ExecutionResultSchema(
                success=False,
                action="CONFIRM",
                intent="CONFIRM",
                message="Confirmation token has expired or is invalid. Please reissue your command."
            )

        diff = pending_data.get('diff_summary', {})
        intent_str = diff.get('intent') or session.pending_action or 'TASK_DELETE'
        entities_dict = diff.get('entities', {}) or session.pending_entities
        target_id = diff.get('target_id')

        # Clear pending token
        ContextManager.clear_pending_confirmation(user_id, token)
        session.confirmation_token = None
        session.confirmation_required = False
        session.pending_action = None
        ContextManager.save_session(session)

        # Build entities
        entities = EntitySchema(**entities_dict)
        if target_id and not entities.task_id:
            entities.task_id = target_id

        # Resolve entity
        resolved = None
        if target_id:
            resolved = Task.objects.filter(id=target_id).first()

        try:
            itype = IntentType(intent_str)
        except ValueError:
            itype = IntentType.UNKNOWN

        result = ToolRegistry.execute(itype, user, entities, resolved)
        result.message = f"Confirmed: {result.message}"
        return result

    @classmethod
    def _handle_cancel(cls, command: CommandSchema, user) -> ExecutionResultSchema:
        user_id = user.id if hasattr(user, 'id') else 0
        session = ContextManager.get_session(user_id, command.conversation_id)
        if session and session.confirmation_token:
            ContextManager.clear_pending_confirmation(user_id, session.confirmation_token)
            session.confirmation_token = None
            session.confirmation_required = False
            session.pending_action = None
            session.candidate_entities = []
            ContextManager.save_session(session)

        return ExecutionResultSchema(
            success=True,
            action="CANCEL",
            intent="CANCEL",
            message="Action cancelled. No changes were made."
        )

    @classmethod
    def _handle_candidate_select(cls, command: CommandSchema, user) -> ExecutionResultSchema:
        user_id = user.id if hasattr(user, 'id') else 0
        session = ContextManager.get_session(user_id, command.conversation_id)

        if not session or not session.candidate_entities:
            return ExecutionResultSchema(
                success=False,
                action="CANDIDATE_SELECT",
                intent="CANDIDATE_SELECT",
                message="No ambiguous items are currently awaiting selection."
            )

        idx = command.entities.extra.get('selected_index')
        candidates = session.candidate_entities
        selected_cand = None

        if idx and 1 <= idx <= len(candidates):
            selected_cand = candidates[idx - 1]
        else:
            # Try fuzzy keyword match with normalized text
            q = command.normalized_text.lower()
            for cand in candidates:
                if cand['title'].lower() in q or any(w in cand['title'].lower() for w in q.split()):
                    selected_cand = cand
                    break

        if not selected_cand:
            cand_lines = [f"{i+1}. #{c['id']} {c['title']}" for i, c in enumerate(candidates)]
            return ExecutionResultSchema(
                success=False,
                action="CANDIDATE_SELECT",
                intent="CANDIDATE_SELECT",
                message=f"I couldn't match your selection. Please choose from:\n" + "\n".join(cand_lines)
            )

        # Clear candidates
        session.candidate_entities = []
        ContextManager.save_session(session)

        # Target task
        task = Task.objects.filter(id=selected_cand['id']).first()
        if not task:
            return ExecutionResultSchema(
                success=False,
                action="CANDIDATE_SELECT",
                intent="CANDIDATE_SELECT",
                message="The selected task no longer exists."
            )

        last_intent = session.last_intent or IntentType.TASK_COMPLETE.value
        try:
            itype = IntentType(last_intent)
        except ValueError:
            itype = IntentType.TASK_COMPLETE

        ent = EntitySchema(task_id=task.id, task_title=task.title)

        # If destructive, stage confirmation
        if itype in (IntentType.TASK_DELETE, IntentType.TASK_UPDATE):
            token = str(uuid.uuid4())[:8]
            preview = ActionPreviewSchema(
                action_type=itype.value,
                title=f"Confirm: {itype.value} '{task.title}'",
                description=f"Are you sure you want to {itype.value.lower().replace('_', ' ')} task #{task.id} '{task.title}'?",
                diff_summary={"intent": itype.value, "target_id": task.id, "target_name": task.title},
                confirm_token=token,
                expires_at=(timezone.now() + timezone.timedelta(minutes=10)).isoformat()
            )
            ContextManager.set_pending_confirmation(user_id, preview)
            ContextManager.update_context(
                user_id=user_id,
                conversation_id=command.conversation_id,
                confirmation_token=token
            )
            return ExecutionResultSchema(
                success=True,
                action=itype.value,
                intent=itype.value,
                requires_confirmation=True,
                preview=preview,
                message=f"Selected task #{task.id} '{task.title}'. Do you want to proceed with {itype.value.lower().replace('_', ' ')}? (Reply 'yes' or 'no')"
            )

        return ToolRegistry.execute(itype, user, ent, task)
