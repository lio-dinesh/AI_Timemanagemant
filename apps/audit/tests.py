from django.test import TestCase
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.audit.services.auditor import AuditService

class AuditTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='audit_user@example.com', username='audit_u', password='pwd')

    def test_audit_log_sanitizes_credentials(self):
        entry = AuditService.log(
            action='LOGIN_ATTEMPT',
            user=self.user,
            resource_type='User',
            resource_id=self.user.id,
            status='SUCCESS',
            metadata={
                'user_email': 'audit_user@example.com',
                'password': 'PlainTextSecretPassword123!',
                'api_key': 'secret-brevo-token-xyz',
                'device': 'Chrome'
            }
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.metadata['password'], '[REDACTED]')
        self.assertEqual(entry.metadata['api_key'], '[REDACTED]')
        self.assertEqual(entry.metadata['device'], 'Chrome')
