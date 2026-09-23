from django.test import TestCase
from apps.accounts.models import User
from apps.ai.services.nlp.evaluator import NLPEvaluator


class NLPEvaluatorTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='eval_user@example.com',
            username='eval_user',
            password='pwd'
        )

    def test_nlp_evaluation_framework(self):
        metrics = NLPEvaluator.evaluate(self.user)

        # Quality Gates
        self.assertGreaterEqual(metrics["intent_accuracy_percent"], 90.0)
        self.assertEqual(metrics["adversarial_rejection_rate_percent"], 100.0)
        self.assertLess(metrics.get("fast_path_avg_latency_ms", metrics["fast_path_latency_ms"]), 50.0)
        self.assertTrue(metrics["passed_quality_gates"])
