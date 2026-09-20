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

        # Extract entities using normalized text
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
