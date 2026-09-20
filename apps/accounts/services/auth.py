from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import authenticate
from apps.accounts.models import User, UserRole

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

class AuthService:
    @staticmethod
    def authenticate_user(request, email, password):
        """
        Authenticates user with account lockout enforcement.
        """
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None, "Invalid credentials."

        # Check if currently locked
        if user.is_locked:
            minutes_left = int((user.locked_until - timezone.now()).total_seconds() / 60) + 1
            return None, f"Account is locked due to too many failed attempts. Try again in {minutes_left} minutes."

        authenticated_user = authenticate(request, username=email, password=password)

        if authenticated_user:
            # Reset failed attempts upon successful login
            if user.failed_login_count > 0 or user.locked_until is not None:
                user.failed_login_count = 0
                user.locked_until = None
                user.save(update_fields=['failed_login_count', 'locked_until'])
            return authenticated_user, None
        else:
            # Increment failed attempts
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_FAILED_ATTEMPTS:
                user.locked_until = timezone.now() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                user.save(update_fields=['failed_login_count', 'locked_until'])
                return None, f"Account locked for {LOCKOUT_DURATION_MINUTES} minutes due to repeated failed login attempts."
            else:
                user.save(update_fields=['failed_login_count'])
                attempts_left = MAX_FAILED_ATTEMPTS - user.failed_login_count
                return None, f"Invalid credentials. {attempts_left} attempts remaining before lockout."

    @staticmethod
    def register_user(email, username, password, first_name="", last_name="", role=UserRole.EMPLOYEE, timezone="UTC"):
        if User.objects.filter(email__iexact=email).exists():
            raise ValueError("A user with this email already exists.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValueError("A user with this username already exists.")

        user = User.objects.create_user(
            email=email,
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            timezone=timezone
        )
        return user
