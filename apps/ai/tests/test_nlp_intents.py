from django.test import TestCase
from apps.ai.services.nlp.intents import (
    IntentType,
    RiskLevel,
    INTENT_REGISTRY,
    get_intent_definition,
    ALL_ROLES,
    MANAGERS_AND_ADMINS,
    ADMINS_ONLY,
)


class NLPIntentsTestCase(TestCase):
    def test_canonical_intent_registry_completeness(self):
        """Verify all IntentType enum entries have registered definitions."""
        for intent in IntentType:
            defn = INTENT_REGISTRY.get(intent)
            self.assertIsNotNone(defn, f"Intent {intent} is missing from INTENT_REGISTRY")
            self.assertEqual(defn.intent, intent)
            self.assertTrue(len(defn.allowed_roles) > 0)
            self.assertTrue(len(defn.tool_method) > 0)
            self.assertTrue(len(defn.description) > 0)

    def test_destructive_intents_require_confirmation(self):
        """Destructive actions must strictly enforce requires_confirmation=True."""
        destructive_intents = [
            IntentType.TASK_DELETE,
            IntentType.SCHEDULE_DELETE,
        ]
        for itype in destructive_intents:
            defn = get_intent_definition(itype.value)
            self.assertIsNotNone(defn)
            self.assertEqual(defn.risk, RiskLevel.DESTRUCTIVE)
            self.assertTrue(defn.requires_confirmation, f"{itype} must require confirmation")

    def test_role_separation(self):
        """Verify privileged operations require MANAGER or ADMIN roles."""
        task_assign = get_intent_definition(IntentType.TASK_ASSIGN.value)
        self.assertIn("MANAGER", task_assign.allowed_roles)
        self.assertNotIn("EMPLOYEE", task_assign.allowed_roles)

        proj_create = get_intent_definition(IntentType.PROJECT_CREATE.value)
        self.assertNotIn("EMPLOYEE", proj_create.allowed_roles)

        # Employee allowed intents
        task_create = get_intent_definition(IntentType.TASK_CREATE.value)
        self.assertIn("EMPLOYEE", task_create.allowed_roles)

    def test_unknown_intent_lookup(self):
        defn = get_intent_definition("NON_EXISTENT_INTENT")
        self.assertIsNone(defn)
