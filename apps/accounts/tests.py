from django.test import TestCase, RequestFactory
from django.utils import timezone
from apps.accounts.models import User, UserRole
from apps.accounts.services.auth import AuthService, MAX_FAILED_ATTEMPTS

class AccountsTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='TestPassword123!',
            role=UserRole.EMPLOYEE
        )

    def test_successful_authentication(self):
        request = self.factory.post('/login/')
        user, err = AuthService.authenticate_user(request, 'test@example.com', 'TestPassword123!')
        self.assertIsNotNone(user)
        self.assertIsNone(err)
        self.assertEqual(user.failed_login_count, 0)

    def test_account_lockout_after_max_failed_attempts(self):
        request = self.factory.post('/login/')
        for _ in range(MAX_FAILED_ATTEMPTS):
            user, err = AuthService.authenticate_user(request, 'test@example.com', 'WrongPassword!')
            self.assertIsNone(user)

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_locked)

        # Attempt login while locked
        user, err = AuthService.authenticate_user(request, 'test@example.com', 'TestPassword123!')
        self.assertIsNone(user)
        self.assertIn("locked", err.lower())

    def test_role_properties(self):
        admin = User.objects.create_user(email='admin_test@example.com', username='adm', password='x', role=UserRole.ADMIN)
        manager = User.objects.create_user(email='mgr_test@example.com', username='mgr', password='x', role=UserRole.MANAGER)
        employee = User.objects.create_user(email='emp_test@example.com', username='emp', password='x', role=UserRole.EMPLOYEE)

        self.assertTrue(admin.is_admin_role)
        self.assertTrue(admin.is_manager_role)
        self.assertTrue(manager.is_manager_role)
        self.assertFalse(manager.is_admin_role)
        self.assertFalse(employee.is_manager_role)
