import re
import logging
import uuid
from typing import Optional, Dict, Any
from apps.ai.schemas import CommandSchema, EntitySchema, CommandSource
from apps.ai.services.nlp.intents import IntentType, get_intent_definition, RiskLevel
from apps.ai.services.nlp.entities import EntityExtractor
from apps.ai.services.nlp.command_router import CommandRouter
from apps.ai.services.nlp.context import ContextManager

logger = logging.getLogger(__name__)


class NLPParser:
    """
    Robust NLP Parser for natural language commands.
    Features:
    - Typo-tolerant lexical normalization.
    - Tiered intent classification (Fast Path & Smart Path).
    - Entity extraction (Dates, times, task names, projects, priorities).
    - Contextual history linking and multi-turn state enrichment.
    """

    TYPO_CORRECTIONS = [
        # Remind typos
        (r'\b(remain|reminde|remindr|remider|rimind|remand)\b', 'remind'),
        # Schedule typos
        (r'\b(scheudle|shedule|scedule|skedule|shedul|schedual)\b', 'schedule'),
        # Time units
        (r'\b(minuts|mintues|minitues|minits|mins)\b', 'minutes'),
        (r'\b(hrs|hour)\b', 'hours'),
        # Meeting typos
        (r'\b(meetign|meting|meetin)\b', 'meeting'),
        # Tomorrow typos
        (r'\b(tomorow|tommorow|tomarrow)\b', 'tomorrow'),
        # Task typos
        (r'\b(taks|tsak|tak)\b', 'task'),
        # Priority typos
        (r'\b(prioirty|priorty|priortiy)\b', 'priority'),
        # Complete typos
        (r'\b(compelte|complet|compelete)\b', 'complete'),
        # Delete typos
        (r'\b(delte|delet|del)\b', 'delete'),
        # Update typos
        (r'\b(updat|updt)\b', 'update'),
    ]

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """
        Cleans and corrects common typos in the input string.
        """
        cleaned = text.strip()
        cleaned_lower = cleaned.lower()

        for pattern, replacement in cls.TYPO_CORRECTIONS:
            cleaned_lower = re.sub(pattern, replacement, cleaned_lower)

        # Collapse redundant whitespace
        cleaned_lower = re.sub(r'\s+', ' ', cleaned_lower).strip()
        return cleaned_lower

    @classmethod
    def parse_with_gemini(cls, raw_text: str, user, normalized: str):
        """
        Invokes Gemini LLM to intelligently extract intent and rich entities
        from natural language prompts, especially task creation and assignment.
        """
        try:
            from django.conf import settings
            from django.utils import timezone
            import json
            from apps.ai.services.llm_provider import get_llm_provider, GeminiLLMProvider
            from apps.accounts.models import User

            provider = get_llm_provider()
            if not isinstance(provider, GeminiLLMProvider):
                return None

            now = timezone.now()
            date_ctx = f"{now.strftime('%Y-%m-%d %H:%M %A')} (ISO: {now.isoformat()})"
            team = list(User.objects.values('id', 'username', 'email', 'first_name', 'last_name')[:20])
            team_str = ", ".join([f"{u['username']} <{u['email']}>" for u in team]) if team else "none"

            system = (
                "You are an expert NLP assistant for the AI Time Management platform.\n"
                f"Current timestamp: {date_ctx}\n"
                f"Current logged-in user: {user.username} <{user.email}>\n"
                f"Available team members: {team_str}\n\n"
                "Extract the user intent and entities. Output MUST be ONLY valid JSON matching this schema:\n"
                "{\n"
                '  "intent": "TASK_CREATE" | "TASK_ASSIGN" | "TASK_COMPLETE" | "TASK_UPDATE" | "TASK_DELETE" | "TASK_SEARCH" | "SCHEDULE_CREATE" | "TIMER_START" | "TIMER_STOP" | "REMINDER_CREATE" | "HELP" | "UNKNOWN",\n'
                '  "confidence": float,\n'
                '  "entities": {\n'
                '    "task_title": string or null,\n'
                '    "description": string or null,\n'
                '    "task_id": int or null,\n'
                '    "priority": int (1-10) or null,\n'
                '    "category": string or null,\n'
                '    "date": "YYYY-MM-DD" or null,\n'
                '    "start_time": "HH:MM" or null,\n'
                '    "user_reference": string or null,\n'
                '    "reminder_minutes": int or null\n'
                "  }\n"
                "}\n\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. If user says 'assign to X' (e.g. 'assign to liodinesh1905@gmail.com' or 'to Dinesh'), set user_reference to that email/name.\n"
                "2. If user assigns to themselves or no assignee specified in task creation, user_reference can be current user's email.\n"
                "3. Compute absolute dates for relative terms (e.g. 'tomorrow' relative to current timestamp).\n"
                "4. Output JSON ONLY, no extra markdown or explanations."
            )

            prompt = f"User input command: {raw_text}"
            res = provider.complete(prompt, system=system)
            if not res:
                return None

            data = json.loads(res)
            intent_str = data.get("intent")
            if not intent_str or intent_str == "UNKNOWN":
                return None

            try:
                valid_intent = IntentType(intent_str)
            except ValueError:
                return None

            g_entities = data.get("entities", {})
            schema_entities = EntitySchema()
            schema_entities.task_title = g_entities.get("task_title")
            schema_entities.task_id = g_entities.get("task_id")
            schema_entities.priority = g_entities.get("priority")
            schema_entities.category = g_entities.get("category") or "WORK"
            schema_entities.date = g_entities.get("date")
            schema_entities.start_time = g_entities.get("start_time")
            schema_entities.user_reference = g_entities.get("user_reference")
            schema_entities.reminder_minutes = g_entities.get("reminder_minutes")
            if g_entities.get("description"):
                schema_entities.extra["description"] = g_entities.get("description")
            schema_entities.extra["gemini_parsed"] = True

            conf = float(data.get("confidence", 0.95))
            return valid_intent, conf, schema_entities
        except Exception as e:
            logger.warning("Gemini parsing bypassed (%s). Falling back to heuristic extractor.", e)
            return None

    @classmethod
    def parse(
        cls,
        raw_text: str,
        user,
        conversation_id: Optional[str] = None,
        source: CommandSource = CommandSource.TEXT
    ) -> CommandSchema:
        """
        Parses raw text into a fully qualified CommandSchema.
        """
        cid = conversation_id or str(uuid.uuid4())
        normalized = cls.normalize_text(raw_text)

        # Route command
        routed_intent, confidence, is_fast_path = CommandRouter.route(normalized)

        # Check for confirmation meta-intents
        if routed_intent in ('CONFIRM', 'CANCEL', 'CANDIDATE_SELECT'):
            intent_str = str(routed_intent)
            entities = EntitySchema()
            if routed_intent == 'CANDIDATE_SELECT':
                # Try to extract candidate index (e.g. "the 2nd one", "number 1", "1")
                idx_match = re.search(r'\b(?:the\s+)?(\d+)(?:st|nd|rd|th)?\b', normalized)
                if not idx_match:
                    word_map = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5}
                    for w, val in word_map.items():
                        if w in normalized:
                            entities.extra['selected_index'] = val
                            break
                else:
                    entities.extra['selected_index'] = int(idx_match.group(1))

            return CommandSchema(
                intent=intent_str,
                raw_text=raw_text,
                normalized_text=normalized,
                user_id=user.id if hasattr(user, 'id') else 0,
                entities=entities,
                conversation_id=cid,
                confidence=confidence,
                risk_level=RiskLevel.LOW_RISK_WRITE.value,
                requires_confirmation=False,
                source=source
            )

        # If fast path, extract with regex extractor immediately
        if is_fast_path:
            entities = EntityExtractor.extract_entities(normalized, user, intent=routed_intent.value if isinstance(routed_intent, IntentType) else None)
        else:
            # Smart Path: try Gemini LLM first for deep contextual comprehension
            gemini_result = cls.parse_with_gemini(raw_text, user, normalized)
            if gemini_result:
                routed_intent, confidence, entities = gemini_result
            else:
                entities = EntityExtractor.extract_entities(normalized, user, intent=routed_intent.value if isinstance(routed_intent, IntentType) else None)

        # Lookup intent metadata
        intent_def = get_intent_definition(routed_intent.value if isinstance(routed_intent, IntentType) else str(routed_intent))
        risk = intent_def.risk.value if intent_def else RiskLevel.LOW_RISK_WRITE.value
        requires_conf = intent_def.requires_confirmation if intent_def else False

        # If previous session has relevant context, merge entities
        user_id = user.id if hasattr(user, 'id') else 0
        session = ContextManager.get_session(user_id, cid)
        if session and session.pending_entities:
            for k, v in session.pending_entities.items():
                if getattr(entities, k, None) is None:
                    setattr(entities, k, v)

        return CommandSchema(
            intent=routed_intent.value if isinstance(routed_intent, IntentType) else str(routed_intent),
            raw_text=raw_text,
            normalized_text=normalized,
            user_id=user.id if hasattr(user, 'id') else 0,
            entities=entities,
            conversation_id=cid,
            confidence=confidence,
            risk_level=risk,
            requires_confirmation=requires_conf,
            source=source
        )
