import logging
from typing import Dict, Any, Optional
from apps.ai.schemas import CommandSource, ExecutionResultSchema
from apps.ai.services.nlp.parser import NLPParser
from apps.ai.services.nlp.executor import NLPExecutor
from apps.ai.services.nlp.response import ResponseGenerator, ResponseValidator

logger = logging.getLogger(__name__)


class NLPCommandService:
    """
    Unified entry point for natural language command processing.
    Delegates to NLPParser, NLPExecutor, ResponseGenerator, and ResponseValidator.
    Preserves backwards compatibility with legacy callers while unlocking full production capabilities.
    """

    @classmethod
    def parse_and_execute(
        cls,
        command_text: str,
        user,
        conversation_id: Optional[str] = None,
        source: str = "TEXT"
    ) -> Dict[str, Any]:
        raw_text = (command_text or "").strip()
        if not raw_text:
            return {
                "success": False,
                "action": "UNKNOWN",
                "intent": "EMPTY_COMMAND",
                "message": "Please enter or speak a command to execute.",
                "data": {},
                "requires_confirmation": False
            }

        cmd_source = CommandSource.VOICE if source.upper() == "VOICE" else CommandSource.TEXT

        try:
            # 1. Parse into structured CommandSchema
            command = NLPParser.parse(
                raw_text=raw_text,
                user=user,
                conversation_id=conversation_id,
                source=cmd_source
            )

            # 2. Authoritative Execution through Policy & ToolRegistry
            result: ExecutionResultSchema = NLPExecutor.execute(command, user)

            # 3. Format conversational response
            formatted_message = ResponseGenerator.format_response(result)

            # 4. Validate output grounding against database result
            ResponseValidator.validate(formatted_message, result)

            # Backwards-compatible action mapping for legacy tests/clients
            action_name = result.action
            if result.action.startswith("SCHEDULE"):
                action_name = "SCHEDULE"
            elif result.action.startswith("REMINDER"):
                action_name = "REMINDER"
            elif result.action.startswith("TIMER"):
                action_name = "TIMER"

            return {
                "success": result.success,
                "action": action_name,
                "canonical_action": result.action,
                "intent": result.intent,
                "message": formatted_message,
                "data": result.data,
                "errors": result.errors,
                "requires_confirmation": result.requires_confirmation,
                "preview": result.preview.to_dict() if result.preview else None,
                "candidates": result.candidates,
                "confidence": result.confidence,
                "conversation_id": command.conversation_id,
                "audit_logged": result.audit_logged
            }

        except Exception as e:
            logger.exception(f"Unexpected error in NLPCommandService: {e}")
            return {
                "success": False,
                "action": "ERROR",
                "intent": "SYSTEM_ERROR",
                "message": f"An error occurred while processing your command: {str(e)}",
                "data": {},
                "requires_confirmation": False
            }
