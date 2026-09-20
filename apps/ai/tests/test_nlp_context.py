from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.ai.services.nlp.context import ContextManager
from apps.ai.schemas import ActionPreviewSchema


class NLPContextTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='ctx_user@example.com', username='ctx_user', password='pwd')
        self.cid = "test_conversation_123"

    def test_session_lifecycle(self):
        # 1. Retrieve initial empty session
        session = ContextManager.get_session(self.user.id, self.cid)
        self.assertEqual(session.conversation_id, self.cid)
        self.assertEqual(session.user_id, self.user.id)
        self.assertIsNone(session.last_intent)

        # 2. Update session with pending entities
        ContextManager.update_context(
            user_id=self.user.id,
            conversation_id=self.cid,
            last_intent="TASK_CREATE",
            pending_entities={"task_title": "Build Architecture"}
        )

        # 3. Retrieve updated session
        updated = ContextManager.get_session(self.user.id, self.cid)
        self.assertEqual(updated.last_intent, "TASK_CREATE")
        self.assertEqual(updated.pending_entities.get("task_title"), "Build Architecture")

        # 4. Clear context
        ContextManager.clear_context(self.user.id, self.cid)
        cleared = ContextManager.get_session(self.user.id, self.cid)
        self.assertIsNone(cleared.last_intent)

    def test_pending_confirmation_staging(self):
        preview = ActionPreviewSchema(
            action_type="TASK_DELETE",
            title="Delete Task",
            description="Are you sure you want to delete task #5?",
            diff_summary={"task_id": 5, "intent": "TASK_DELETE"},
            confirm_token="token_abc_123",
            expires_at=(timezone.now() + timezone.timedelta(minutes=10)).isoformat()
        )

        # Stage confirmation
        token = ContextManager.set_pending_confirmation(self.user.id, preview)
        self.assertEqual(token, "token_abc_123")

        # Retrieve staged confirmation
        staged = ContextManager.get_pending_confirmation(self.user.id, token)
        self.assertIsNotNone(staged)
        self.assertEqual(staged["action_type"], "TASK_DELETE")
        self.assertEqual(staged["diff_summary"]["task_id"], 5)

        # Clear staged confirmation
        ContextManager.clear_pending_confirmation(self.user.id, token)
        self.assertIsNone(ContextManager.get_pending_confirmation(self.user.id, token))
