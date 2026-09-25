import re
import logging
from enum import Enum
from typing import Dict, Any, Optional, List
from apps.ai.schemas import ExecutionResultSchema

logger = logging.getLogger(__name__)


class ResponseMode(str, Enum):
    ACTION = "ACTION"
    ANALYTICAL = "ANALYTICAL"
    CLARIFICATION = "CLARIFICATION"
    CONFIRMATION = "CONFIRMATION"
    RECOMMENDATION = "RECOMMENDATION"
    ERROR = "ERROR"


class ResponseGenerator:
    """
    Synthesizes user-facing conversational responses grounded strictly in ExecutionResultSchema.
    Zero hallucination guarantee: Never invents numbers or facts not in result data.
    """

    @classmethod
    def format_response(
        cls,
        result: ExecutionResultSchema,
        mode: Optional[ResponseMode] = None
    ) -> str:
        # Determine mode automatically if not provided
        if not mode:
            if not result.success:
                mode = ResponseMode.ERROR
            elif result.requires_confirmation:
                mode = ResponseMode.CONFIRMATION
            elif result.candidates:
                mode = ResponseMode.CLARIFICATION
            elif result.action in ("PRODUCTIVITY_SUMMARY", "PRODUCTIVITY_TREND", "PRODUCTIVITY_PATTERN", "TIME_ANALYSIS"):
                mode = ResponseMode.ANALYTICAL
            elif result.action in ("AI_RECOMMENDATION", "AI_SCHEDULE"):
                mode = ResponseMode.RECOMMENDATION
            else:
                mode = ResponseMode.ACTION

        # Base message is authoritative
        raw_msg = result.message

        if mode == ResponseMode.CONFIRMATION and result.preview:
            return f"⚠️ **Confirmation Required**\n\n{result.preview.description}\n\n*Reply with **'yes'** or **'confirm'** to proceed, or **'no'** to cancel.*"

        elif mode == ResponseMode.CLARIFICATION and result.candidates:
            if "\n1. #" in raw_msg or "\n- **" in raw_msg:
                return raw_msg
            cands_text = "\n".join([
                f"- **{i+1}.** {c.get('title', 'Untitled')} (ID: #{c.get('id', '-')})"
                for i, c in enumerate(result.candidates)
            ])
            return f"{raw_msg}\n\n{cands_text}\n\n*Which one would you like to select? (e.g. 'the first one' or 'number 1')*"

        elif mode == ResponseMode.ANALYTICAL and result.data:
            # Grounded analytical summary
            return raw_msg

        return raw_msg


class ResponseValidator:
    """
    Evaluates response consistency against ground-truth database output.
    Flags or corrects hallucinations.
    """

    @classmethod
    def validate(cls, response_text: str, result: ExecutionResultSchema) -> bool:
        """
        Returns True if response contains no contradictory or fabricated claims.
        """
        # 1. Error state consistency
        if not result.success:
            # Response should not claim success
            if re.search(r'\b(successfully|created task|timer started|completed)\b', response_text, re.IGNORECASE):
                logger.warning("ResponseValidator flag: Response claims success despite execution failure.")
                return False

        # 2. Key entity grounding (e.g. ID verification)
        if result.data.get('task_id'):
            tid = str(result.data['task_id'])
            # If an ID is mentioned in text, verify it matches
            ids_in_text = re.findall(r'#(\d+)', response_text)
            for found_id in ids_in_text:
                if found_id != tid and result.data.get('task_id') is not None:
                    # Mismatched ID hallucination
                    logger.warning(f"ResponseValidator flag: Hallucinated task ID #{found_id} vs actual #{tid}")
                    return False

        return True
