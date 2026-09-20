import re
import logging
from typing import Tuple, Optional
from apps.ai.services.nlp.intents import IntentType

logger = logging.getLogger(__name__)


class CommandRouter:
    """
    Two-tier router for natural language commands:
    Tier 1 (Fast Path): <25ms, zero LLM cost, deterministic pattern matching for high-frequency queries.
    Tier 2 (Smart Path): Robust intent classification heuristics and context-aware resolution.
    """

    # Fast Path exact/near-exact patterns
    FAST_PATH_RULES = [
        # Timer
        (r'^(?:start|begin)\s+timer$', IntentType.TIMER_START),
        (r'^(?:stop|end|pause)\s+timer$', IntentType.TIMER_STOP),

        # Tasks List
        (r'^(?:show|list|get|view)\s+(?:all\s+)?(?:my\s+)?tasks$', IntentType.TASK_LIST),
        (r'^(?:my\s+tasks|pending\s+tasks|active\s+tasks)$', IntentType.TASK_LIST),

        # Schedule
        (r'^(?:show|get|view|check)\s+(?:my\s+)?schedule$', IntentType.SCHEDULE_SEARCH),
        (r'^(?:my\s+schedule|today\'?s?\s+schedule|what(?:\'s|\s+is)\s+on\s+my\s+schedule(?:\s+today)?)$', IntentType.SCHEDULE_SEARCH),

        # Free Time
        (r'^(?:free\s+(?:time|slots)|how\s+much\s+free\s+time(?:\s+do\s+i\s+have)?(?:\s+today)?)$', IntentType.AI_TIME_ALLOCATION),

        # Reminders
        (r'^(?:show|list|view|get)\s+(?:my\s+)?reminders$', IntentType.REMINDER_LIST),

        # Notifications
        (r'^(?:show|list|view|get)\s+(?:my\s+)?notifications$', IntentType.NOTIFICATION_LIST),
        (r'^(?:mark\s+(?:all\s+)?notifications?\s+(?:as\s+)?read)$', IntentType.NOTIFICATION_READ),

        # Productivity Summary
        (r'^(?:productivity\s+summary|my\s+productivity|how\s+productive\s+was\s+i(?:\s+today)?)$', IntentType.PRODUCTIVITY_SUMMARY),

        # AI Recommendations / Planning
        (r'^(?:recommendations?|ai\s+recommendations?|what\s+should\s+i\s+work\s+on)$', IntentType.AI_RECOMMENDATION),
        (r'^(?:plan\s+my\s+day|optimize\s+(?:my\s+)?schedule)$', IntentType.AI_SCHEDULE),

        # Help
        (r'^(?:help|what\s+can\s+you\s+do|commands|\?)$', IntentType.HELP),
    ]

    # Smart Path Regex patterns for intent identification
    SMART_PATTERNS = [
        # Confirmations & Cancellations (special meta-intents)
        (r'^(?:yes|confirm|proceed|do\s+it|approve|sure|ok|yep)$', 'CONFIRM'),
        (r'^(?:no|cancel|abort|stop|reject|nevermind|nope)$', 'CANCEL'),
        (r'^(?:the\s+)?(?:first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|one|\#\d+|\d+)\s*(?:one)?$', 'CANDIDATE_SELECT'),

        # Destructive Task / Schedule Operations (require high certainty)
        (r'\b(?:delete|remove|destroy|trash)\s+(?:the\s+)?task\b', IntentType.TASK_DELETE),
        (r'\b(?:delete|cancel|remove)\s+(?:the\s+)?(?:meeting|event|schedule|session)\b', IntentType.SCHEDULE_DELETE),

        # Task Operations
        (r'\b(?:complete|finish|mark\s+(?:as\s+)?done|mark\s+complete|done\s+with)\b', IntentType.TASK_COMPLETE),
        (r'\b(?:create|add|new)\s+(?:a\s+)?(?:new\s+)?task\b', IntentType.TASK_CREATE),
        (r'\b(?:update|change|reschedule|edit|modify)\s+(?:the\s+)?task\b', IntentType.TASK_UPDATE),
        (r'\b(?:assign|delegate)\s+(?:the\s+)?task\b', IntentType.TASK_ASSIGN),
        (r'\b(?:find|search|lookup)\s+(?:for\s+)?(?:a\s+)?task\b', IntentType.TASK_SEARCH),
        (r'\b(?:show|list|display)\s+(?:my\s+)?tasks\b', IntentType.TASK_LIST),

        # Project Operations
        (r'\b(?:create|add|new)\s+(?:a\s+)?project\b', IntentType.PROJECT_CREATE),
        (r'\b(?:update|change|reschedule)\s+(?:the\s+)?project\b', IntentType.PROJECT_UPDATE),
        (r'\b(?:find|search|show|list)\s+projects?\b', IntentType.PROJECT_SEARCH),

        # Reminders & Alerts (including "remain me" typo handling)
        (r'\b(?:remind|reminder|alert|notify|alarm|ping)\b', IntentType.REMINDER_CREATE),
        (r'\b\d+\s*(?:minutes?|hours?|m|h)?\s+before\b', IntentType.REMINDER_CREATE),
        (r'\b(?:dismiss|delete|cancel|remove)\s+(?:the\s+)?reminder\b', IntentType.REMINDER_DELETE),
        (r'\b(?:show|list)\s+reminders?\b', IntentType.REMINDER_LIST),

        # Timer Operations
        (r'\b(?:start|begin)\s+(?:a\s+)?timer\b', IntentType.TIMER_START),
        (r'\b(?:stop|end|pause)\s+(?:the\s+)?timer\b', IntentType.TIMER_STOP),
        (r'\b(?:log|record|add)\s+(?:\d+\s*(?:hours?|hrs?|mins?|minutes?))\s+(?:on|for)\b', IntentType.TIME_ENTRY_CREATE),
        (r'\b(?:time\s+history|tracked\s+time|time\s+spent|time\s+log)\b', IntentType.TIME_HISTORY),
        (r'\b(?:analyze\s+time|time\s+breakdown|time\s+analysis)\b', IntentType.TIME_ANALYSIS),

        # Scheduling Operations
        (r'\b(?:schedule|book|block\s+time|set\s+up\s+(?:a\s+)?meeting)\b', IntentType.SCHEDULE_CREATE),
        (r'\b(?:reschedule|move|postpone)\s+(?:the\s+)?(?:meeting|event|session)\b', IntentType.SCHEDULE_UPDATE),
        (r'\b(?:check\s+conflicts?|any\s+conflicts?|am\s+i\s+free|is\s+there\s+a\s+conflict)\b', IntentType.SCHEDULE_CONFLICT_CHECK),
        (r'\b(?:schedule|calendar|agenda|what(?:\'s|\s+is)\s+my\s+schedule)\b', IntentType.SCHEDULE_SEARCH),

        # Productivity & Analytics
        (r'\b(?:productivity\s+trend|trend|am\s+i\s+improving)\b', IntentType.PRODUCTIVITY_TREND),
        (r'\b(?:productivity\s+pattern|peak\s+hours|best\s+time\s+to\s+work|focus\s+pattern)\b', IntentType.PRODUCTIVITY_PATTERN),
        (r'\b(?:productivity|productive|score)\b', IntentType.PRODUCTIVITY_SUMMARY),
        (r'\b(?:anomal(?:y|ies)|unusual|burnout|fatigue|odd\s+session)\b', IntentType.ANOMALY_ANALYSIS),

        # Reports
        (r'\b(?:send|email|generate|dispatch)\s+(?:my\s+)?(?:productivity\s+)?report\b', IntentType.REPORT_GENERATE),
        (r'\b(?:report\s+summary|view\s+report)\b', IntentType.REPORT_SUMMARY),

        # AI Planning
        (r'\b(?:optimize|plan)\s+(?:my\s+)?(?:day|schedule)\b', IntentType.AI_SCHEDULE),
        (r'\b(?:free\s+slots?|unallocated\s+time|open\s+time)\b', IntentType.AI_TIME_ALLOCATION),
        (r'\b(?:recommend|suggest|advice)\b', IntentType.AI_RECOMMENDATION),

        # Help
        (r'\b(?:help|commands|options|what\s+can\s+you\s+do)\b', IntentType.HELP),
    ]

    @classmethod
    def route(cls, normalized_text: str) -> Tuple[IntentType, float, bool]:
        """
        Routes the command to an IntentType.
        Returns:
            (IntentType, confidence: float, is_fast_path: bool)
        """
        cleaned = normalized_text.strip().lower()

        # 1. Check Fast Path (<25ms)
        for pattern, intent in cls.FAST_PATH_RULES:
            if re.match(pattern, cleaned, re.IGNORECASE):
                return intent, 1.0, True

        # 2. Check Smart Path patterns
        for pattern, intent_val in cls.SMART_PATTERNS:
            if re.search(pattern, cleaned, re.IGNORECASE):
                if isinstance(intent_val, IntentType):
                    return intent_val, 0.92, False
                elif intent_val in ('CONFIRM', 'CANCEL', 'CANDIDATE_SELECT'):
                    # Special meta-intent markers
                    return intent_val, 0.95, False

        # 3. Fallback
        return IntentType.UNKNOWN, 0.2, False
