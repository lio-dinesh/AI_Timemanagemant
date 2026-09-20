import datetime
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.tasks.models import Task, TaskStatus
from apps.projects.models import Project
from apps.ai.schemas import EntitySchema, ContextSessionSchema
from apps.ai.services.nlp.resolver import EntityResolver


class NLPResolutionTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='resolver_user@example.com', username='resolver_user', password='pwd')
        now = timezone.now()
        self.task1 = Task.objects.create(
            title="Refactor Authentication API",
            assigned_to=self.user,
            created_by=self.user,
            priority=8,
            deadline=now + datetime.timedelta(days=2),
            status=TaskStatus.TODO
        )
        self.task2 = Task.objects.create(
            title="Refactor Billing API",
            assigned_to=self.user,
            created_by=self.user,
            priority=6,
            deadline=now + datetime.timedelta(days=2),
            status=TaskStatus.TODO
        )

    def test_direct_id_resolution(self):
        ent = EntitySchema(task_id=self.task1.id)
        resolved, candidates, conf = EntityResolver.resolve_task(self.user, ent)
        self.assertEqual(resolved, self.task1)
        self.assertEqual(len(candidates), 0)
        self.assertEqual(conf, 1.0)

    def test_single_match_by_keyword(self):
        ent = EntitySchema(task_title="Authentication")
        resolved, candidates, conf = EntityResolver.resolve_task(self.user, ent)
        self.assertEqual(resolved, self.task1)
        self.assertEqual(len(candidates), 0)
        self.assertGreaterEqual(conf, 0.90)

    def test_ambiguous_matches_produce_candidate_list(self):
        ent = EntitySchema(task_title="Refactor")
        resolved, candidates, conf = EntityResolver.resolve_task(self.user, ent)
        # Should NOT guess; must return None with candidate options
        self.assertIsNone(resolved)
        self.assertEqual(len(candidates), 2)
        candidate_ids = [c["id"] for c in candidates]
        self.assertIn(self.task1.id, candidate_ids)
        self.assertIn(self.task2.id, candidate_ids)

    def test_contextual_disambiguation(self):
        session = ContextSessionSchema(
            conversation_id="conv_1",
            user_id=self.user.id,
            candidate_entities=[
                {"id": self.task1.id, "title": self.task1.title},
                {"id": self.task2.id, "title": self.task2.title},
            ]
        )
        ent = EntitySchema(task_title="billing")
        resolved, candidates, conf = EntityResolver.resolve_task(self.user, ent, session=session)
        self.assertEqual(resolved, self.task2)
        self.assertEqual(len(candidates), 0)
