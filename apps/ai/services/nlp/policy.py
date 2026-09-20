import re
from typing import Tuple, Optional
from django.core.cache import cache
from apps.ai.schemas import CommandSchema
from .intents import get_intent_definition, RiskLevel, IntentDefinition


class SecurityViolationError(Exception):
    pass


class PolicyEngine:
    INJECTION_PATTERNS = [
        r'\bignore\s+(all\s+)?(?:previous|prior)\s+instructions\b',
        r'\bsystem\s+prompt\b',
        r'\bdrop\s+table\b',
        r'\bdelete\s+from\s+users\b',
        r'\bgrant\s+admin\b',
        r'\bmake\s+me\s+admin\b',
        r'\bexecute\s+sql\b',
        r'\bselect\s+\*\s+from\b',
        r'<\s*script\b',
        r'\beval\s*\(',
    ]

    @classmethod
    def sanitize_input(cls, raw_text: str) -> Tuple[bool, str, Optional[str]]:
        """
        Scans for prompt-injection, adversarial instruction overrides, and XSS.
        Returns: (is_safe, sanitized_text, error_message)
        """
        text = raw_text.strip()
        lower = text.lower()

        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, lower):
                return False, text, f"Unsafe instruction pattern detected matching security policy."

        # Strip HTML tags
        clean_text = re.sub(r'<[^>]*?>', '', text)
        return True, clean_text, None

    @classmethod
    def check_rate_limit(cls, user_id: int, is_heavy_ai: bool = False) -> Tuple[bool, Optional[str]]:
        """Enforces sliding rate limits per user."""
        key = f"nlp_rate:{user_id}:heavy" if is_heavy_ai else f"nlp_rate:{user_id}:std"
        limit = 5 if is_heavy_ai else 30
        current = cache.get(key, 0)

        if current >= limit:
            return False, f"Rate limit reached ({limit} requests/minute). Please slow down."

        cache.set(key, current + 1, timeout=60)
        return True, None

    @classmethod
    def authorize_command(
        cls,
        command: CommandSchema,
        user
    ) -> Tuple[bool, Optional[str], Optional[IntentDefinition]]:
        """
        Evaluates RBAC, object ownership, and risk levels against the target intent.
        Returns: (authorized, rejection_reason, intent_def)
        """
        intent_def = get_intent_definition(command.intent)
        if not intent_def:
            return False, f"Unknown or unregistered intent: '{command.intent}'", None

        # 1. RBAC Role check
        user_role = getattr(user, 'role', 'EMPLOYEE') or 'EMPLOYEE'
        if user_role not in intent_def.allowed_roles:
            return False, f"Access Restricted: Role '{user_role}' is not authorized to execute {command.intent}.", intent_def

        # 2. Manager / Cross-user check for Team data
        if command.entities.user_reference and not (user.is_manager_role or user.is_admin_role):
            return False, "Access Restricted: Only Managers and Admins can query team or peer records.", intent_def

        # 3. Destructive confirmation requirement
        if intent_def.risk == RiskLevel.DESTRUCTIVE and not command.confirmation_token:
            command.requires_confirmation = True

        return True, None, intent_def
