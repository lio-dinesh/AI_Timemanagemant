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

    def test_login_page_renders_successfully(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign In')
        self.assertContains(response, 'AI')
        self.assertContains(response, 'TimeSync')

    def test_register_page_renders_successfully(self):
        response = self.client.get('/register/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Your Account')

    def test_health_check_endpoint(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('status', data)

    def test_simultaneous_users_isolated_sessions(self):
        from django.test import Client
        user1 = self.user
        user2 = User.objects.create_user(
            email='user2@example.com',
            username='user2',
            password='TestPassword123!',
            role=UserRole.EMPLOYEE
        )

        client1 = Client()
        client2 = Client()

        # User 1 logs in
        login1 = client1.login(email=user1.email, password='TestPassword123!')
        self.assertTrue(login1)

        # User 2 logs in simultaneously
        login2 = client2.login(email=user2.email, password='TestPassword123!')
        self.assertTrue(login2)

        # Verify client1 sees user1 and client2 sees user2 independently
        resp1 = client1.get('/profile/')
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.wsgi_request.user.id, user1.id)

        resp2 = client2.get('/profile/')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.wsgi_request.user.id, user2.id)

        # Verify logout on client1 does NOT affect client2
        client1.get('/logout/')
        resp1_after = client1.get('/profile/')
        self.assertEqual(resp1_after.status_code, 302)  # Redirects to login

        resp2_still_active = client2.get('/profile/')
        self.assertEqual(resp2_still_active.status_code, 200)  # User 2 session still authenticated!
