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
    def parse_with_gemini(cls, raw_text: str, user, normalized: str, session: Optional[Any] = None):
        """
        Invokes Gemini LLM to intelligently extract intent and rich entities
        from natural language prompts with multi-turn conversational context,
        timezone awareness, and pronoun resolution.
        """
        try:
            from django.conf import settings
            from django.utils import timezone
            import json
            import re
            from apps.ai.services.llm_provider import get_llm_provider, GeminiLLMProvider
            from apps.accounts.models import User
            from apps.tracking.models import TimeEntry, TimeEntryStatus

            provider = get_llm_provider()
            if not isinstance(provider, GeminiLLMProvider):
                return None

            # Calculate user's local time based on their configured timezone
            tz_name = getattr(user, 'timezone', None) or 'UTC'
            try:
                import zoneinfo
                user_tz = zoneinfo.ZoneInfo(tz_name)
            except Exception:
                try:
                    import pytz
                    user_tz = pytz.timezone(tz_name)
                except Exception:
                    user_tz = timezone.utc

            now_local = timezone.now().astimezone(user_tz)
            date_ctx = f"{now_local.strftime('%Y-%m-%d %H:%M:%S %A')} (Timezone: {tz_name})"
            tomorrow_date = (now_local + timezone.timedelta(days=1)).strftime('%Y-%m-%d')
            tomorrow_day = (now_local + timezone.timedelta(days=1)).strftime('%A')
            yesterday_date = (now_local - timezone.timedelta(days=1)).strftime('%Y-%m-%d')

            team = list(User.objects.values('id', 'username', 'email', 'first_name', 'last_name')[:20])
            team_str = ", ".join([f"{u['username']} <{u['email']}>" for u in team]) if team else "none"

            # Check active timer status for context
            active_entry = TimeEntry.objects.filter(user=user, status=TimeEntryStatus.OPEN).select_related('task').first()
            if active_entry:
                task_name = active_entry.task.title if active_entry.task else "Untracked Session"
                timer_ctx = f"RUNNING on task '{task_name}' (ID: #{active_entry.task_id})"
            else:
                timer_ctx = "STOPPED (No active timer)"

            # Build multi-turn dialogue context
            dialogue_ctx = "None (first turn)"
            last_task_ctx = "None"
            last_event_ctx = "None"
            if session:
                if session.dialogue_history:
                    turns = []
                    for t in session.dialogue_history[-4:]:
                        turns.append(f"User: {t.get('user', '')}")
                        turns.append(f"Assistant: {t.get('assistant', '')}")
                    dialogue_ctx = "\n".join(turns)
                if session.last_task_title or session.last_task_id:
                    last_task_ctx = f"#{session.last_task_id or '?'} '{session.last_task_title or ''}'"
                if session.last_event_title or session.last_event_id:
                    last_event_ctx = f"#{session.last_event_id or '?'} '{session.last_event_title or ''}'"

            system = (
                "You are TimeSync AI, an intelligent personal time-management and scheduling assistant.\n"
                f"Current User Timestamp: {date_ctx}\n"
                f"Tomorrow's Date: {tomorrow_date} ({tomorrow_day})\n"
                f"Yesterday's Date: {yesterday_date}\n"
                f"Active Timer Status: {timer_ctx}\n"
                f"Last Referenced Task in Conversation: {last_task_ctx}\n"
                f"Last Referenced Schedule Event: {last_event_ctx}\n"
                f"Recent Dialogue History:\n{dialogue_ctx}\n"
                f"Current logged-in user: {user.username} <{user.email}>\n"
                f"Available team members: {team_str}\n\n"
                "Your job is to understand the user's natural language command, resolve pronouns and relative times, and output structured JSON.\n\n"
                "VALID INTENT VALUES:\n"
                "- TASK_CREATE: creating or adding a new task (e.g. 'create a Django task tomorrow at 5pm', 'add a task called review pull request')\n"
                "- TASK_COMPLETE: marking a task as done/complete (e.g. 'complete my Python task', 'finish task #3', 'done with it')\n"
                "- TASK_UPDATE: changing priority, deadline, or title of a task\n"
                "- TASK_DELETE: deleting a task (requires confirmation)\n"
                "- TASK_LIST: listing/showing tasks (e.g. 'show my tasks for tomorrow', 'list my tasks')\n"
                "- TASK_SEARCH: finding a specific task by query\n"
                "- TASK_ASSIGN: delegating a task to another user\n"
                "- SCHEDULE_CREATE: booking/scheduling a focus block, event, or meeting (e.g. 'schedule Python for tomorrow morning', 'block 2 hours for deep work')\n"
                "- SCHEDULE_UPDATE: rescheduling/moving an event or task (e.g. 'move it to Friday', 'make it 6pm instead', 'reschedule to 3pm')\n"
                "- SCHEDULE_DELETE: cancelling a scheduled event\n"
                "- SCHEDULE_SEARCH: checking agenda/calendar (e.g. 'show my schedule', 'what is on my schedule today')\n"
                "- SCHEDULE_CONFLICT_CHECK: checking if free or conflicting\n"
                "- TIMER_START: starting timer (e.g. 'start my timer', 'begin timer on Python')\n"
                "- TIMER_STOP: stopping timer (e.g. 'stop my timer', 'stop it', 'pause timer')\n"
                "- REMINDER_CREATE: setting a reminder/alert (e.g. 'remind me tomorrow at 10pm to submit my assignment', 'remind me in 30 minutes to check database', 'remind me 30 minutes before my meeting')\n"
                "- REMINDER_LIST: viewing reminders\n"
                "- PRODUCTIVITY_SUMMARY: checking today's productivity/score (e.g. 'how productive was I today?', 'productivity summary')\n"
                "- PRODUCTIVITY_TREND: checking 7-day trend\n"
                "- AI_RECOMMENDATION: asking for recommendations/next steps (e.g. 'what should I work on next?', 'what next?')\n"
                "- AI_SCHEDULE: optimizing day/schedule (e.g. 'plan my day')\n"
                "- AI_TIME_ALLOCATION: checking free time slots\n"
                "- HELP: help or command options\n"
                "- UNKNOWN: completely unrecognized\n\n"
                "CRITICAL RULES:\n"
                "1. PRONOUN RESOLUTION: If the user says 'move it to Friday', 'make it 6pm instead', or 'complete it', 'it' refers to the Last Referenced Task or Event.\n"
                "2. 'stop it' ALWAYS maps to TIMER_STOP when timer is running or idle.\n"
                "3. 'start my timer' maps to TIMER_START.\n"
                "4. DATES: Calculate absolute dates in YYYY-MM-DD relative to Current User Timestamp. E.g. 'tomorrow' -> use Tomorrow's Date. 'Friday' -> find next occurrence.\n"
                "5. TIMES: Convert times to 24-hour HH:MM format. '10pm'/'10 tonight' -> '22:00', '5pm' -> '17:00', '6pm' -> '18:00', 'morning' -> '09:00', 'afternoon' -> '14:00', 'evening' -> '18:00', 'tonight' -> '20:00'. If ambiguous 'at 5', default to '17:00' if current time is daytime.\n"
                "6. RELATIVE REMINDERS: If user says 'in 30 minutes' or '30 minutes before', set 'reminder_minutes': 30.\n"
                "7. MULTI-TURN: If recent dialogue shows assistant asked for a time/date and user replied 'Tomorrow at 5', treat as SCHEDULE_CREATE or TASK_UPDATE for the pending task!\n\n"
                "OUTPUT JSON FORMAT (ONLY valid JSON, NO markdown fences):\n"
                "{\n"
                '  "intent": "<VALID_INTENT>",\n'
                '  "confidence": 0.95,\n'
                '  "entities": {\n'
                '    "task_title": string or null,\n'
                '    "description": string or null,\n'
                '    "task_id": int or null,\n'
                '    "priority": int (1-10) or null,\n'
                '    "category": string or null,\n'
                '    "date": "YYYY-MM-DD" or null,\n'
                '    "start_time": "HH:MM" or null,\n'
                '    "end_time": "HH:MM" or null,\n'
                '    "user_reference": string or null,\n'
                '    "reminder_minutes": int or null\n'
                "  }\n"
                "}"
            )

            prompt = f"User input command: {raw_text}"
            res = provider.complete(prompt, system=system)
            if not res:
                return None

            clean_res = res.strip()
            if clean_res.startswith('```'):
                clean_res = re.sub(r'^```(?:json)?\s*', '', clean_res)
                clean_res = re.sub(r'\s*```$', '', clean_res)

            data = json.loads(clean_res)
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
            schema_entities.end_time = g_entities.get("end_time")
            schema_entities.user_reference = g_entities.get("user_reference")
            schema_entities.reminder_minutes = g_entities.get("reminder_minutes")
            if g_entities.get("description"):
                schema_entities.extra["description"] = g_entities.get("description")
            schema_entities.extra["gemini_parsed"] = True
            schema_entities.extra["raw_text"] = raw_text

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
        user_id = user.id if hasattr(user, 'id') else 0
        session = ContextManager.get_session(user_id, cid)

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
                user_id=user_id,
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
            gemini_result = cls.parse_with_gemini(raw_text, user, normalized, session=session)
            if gemini_result:
                routed_intent, confidence, entities = gemini_result
            else:
                entities = EntityExtractor.extract_entities(normalized, user, intent=routed_intent.value if isinstance(routed_intent, IntentType) else None)

        # Lookup intent metadata
        intent_def = get_intent_definition(routed_intent.value if isinstance(routed_intent, IntentType) else str(routed_intent))
        risk = intent_def.risk.value if intent_def else RiskLevel.LOW_RISK_WRITE.value
        requires_conf = intent_def.requires_confirmation if intent_def else False

        # If previous session has relevant context, merge entities
        if session and session.pending_entities:
            for k, v in session.pending_entities.items():
                if getattr(entities, k, None) is None:
                    setattr(entities, k, v)

        return CommandSchema(
            intent=routed_intent.value if isinstance(routed_intent, IntentType) else str(routed_intent),
            raw_text=raw_text,
            normalized_text=normalized,
            user_id=user_id,
            entities=entities,
            conversation_id=cid,
            confidence=confidence,
            risk_level=risk,
            requires_confirmation=requires_conf,
            source=source
        )
