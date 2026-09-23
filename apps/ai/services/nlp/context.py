import json
import uuid
from typing import Optional, Dict, Any, List
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from apps.ai.schemas import ContextSessionSchema, ActionPreviewSchema

# Default TTL: 30 minutes (1800s), fully configurable
NLP_CONTEXT_TTL_SECONDS = getattr(settings, 'NLP_CONTEXT_TTL_SECONDS', 1800)


class ContextManager:
    @staticmethod
    def _make_key(user_id: int, conversation_id: str) -> str:
        return f"nlp_context:{user_id}:{conversation_id}"

    @staticmethod
    def _make_confirm_key(user_id: int, token: str) -> str:
        return f"nlp_confirm:{user_id}:{token}"

    @classmethod
    def get_session(cls, user_id: int, conversation_id: str) -> ContextSessionSchema:
        """Retrieves active conversation context from cache or initializes new session."""
        key = cls._make_key(user_id, conversation_id)
        try:
            data = cache.get(key)
            if data:
                if isinstance(data, str):
                    data = json.loads(data)
                return ContextSessionSchema(**data)
        except Exception:
            pass

        now_str = timezone.now().isoformat()
        return ContextSessionSchema(
            conversation_id=conversation_id,
            user_id=user_id,
            created_at=now_str
        )

    @classmethod
    def save_session(cls, session: ContextSessionSchema) -> None:
        """Saves session state to cache with configurable TTL."""
        key = cls._make_key(session.user_id, session.conversation_id)
        try:
            cache.set(key, session.to_dict(), timeout=NLP_CONTEXT_TTL_SECONDS)
        except Exception:
            pass

    @classmethod
    def update_context(
        cls,
        user_id: int,
        conversation_id: str,
        last_intent: Optional[str] = None,
        pending_action: Optional[str] = None,
        pending_entities: Optional[Dict[str, Any]] = None,
        candidate_entities: Optional[List[Dict[str, Any]]] = None,
        confirmation_token: Optional[str] = None
    ) -> ContextSessionSchema:
        session = cls.get_session(user_id, conversation_id)
        if last_intent is not None:
            session.last_intent = last_intent
        if pending_action is not None:
            session.pending_action = pending_action
        if pending_entities is not None:
            session.pending_entities.update(pending_entities)
        if candidate_entities is not None:
            session.candidate_entities = candidate_entities
        if confirmation_token is not None:
            session.confirmation_token = confirmation_token
            session.confirmation_required = bool(confirmation_token)

        cls.save_session(session)
        return session

    @classmethod
    def clear_context(cls, user_id: int, conversation_id: str) -> None:
        key = cls._make_key(user_id, conversation_id)
        try:
            cache.delete(key)
        except Exception:
            pass

    @classmethod
    def set_pending_confirmation(
        cls,
        user_id: int,
        preview: ActionPreviewSchema,
        timeout: int = 600
    ) -> str:
        """Stores a staged action requiring explicit user confirmation for 10 minutes."""
        key = cls._make_confirm_key(user_id, preview.confirm_token)
        try:
            cache.set(key, preview.to_dict(), timeout=timeout)
        except Exception:
            pass
        return preview.confirm_token

    @classmethod
    def get_pending_confirmation(cls, user_id: int, token: str) -> Optional[Dict[str, Any]]:
        key = cls._make_confirm_key(user_id, token)
        try:
            return cache.get(key)
        except Exception:
            return None

    @classmethod
    def clear_pending_confirmation(cls, user_id: int, token: str) -> None:
        key = cls._make_confirm_key(user_id, token)
        try:
            cache.delete(key)
        except Exception:
            pass
