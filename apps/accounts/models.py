from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import time


class UserRole(models.TextChoices):
    EMPLOYEE = 'EMPLOYEE', 'Employee'
    MANAGER = 'MANAGER', 'Manager'
    ADMIN = 'ADMIN', 'Administrator'


def default_work_days():
    # 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday
    return [0, 1, 2, 3, 4]


def default_preferences():
    return {
        "preferred_focus_duration": 50,  # minutes
        "break_duration": 10,           # minutes
        "preferred_meeting_window": "afternoon",  # morning / afternoon
        "preferred_work_hours": "09:00-17:00",
        "preferred_task_scheduling_behavior": "balanced",
        "productivity_preferences": {
            "track_idle": True,
            "idle_threshold_seconds": 300,
            "auto_categorize": True,
        }
    }


def default_notification_preferences():
    return {
        "email_enabled": True,
        "in_app_enabled": True,
        "task_deadline_reminders": True,
        "meeting_reminders": True,
        "daily_summary": True,
        "productivity_alerts": True,
        "ai_recommendations": True,
    }


class User(AbstractUser):
    email = models.EmailField('email address', unique=True)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.EMPLOYEE,
        db_index=True
    )
    manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinates'
    )
    timezone = models.CharField(max_length=64, default='UTC')
    work_start_time = models.TimeField(default=time(9, 0))
    work_end_time = models.TimeField(default=time(17, 0))
    work_days = models.JSONField(default=default_work_days)
    preferences = models.JSONField(default=default_preferences)
    notification_preferences = models.JSONField(default=default_notification_preferences)

    # Security & Lockout
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['manager']),
        ]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"

    @property
    def is_admin_role(self):
        return self.role == UserRole.ADMIN or self.is_superuser

    @property
    def is_manager_role(self):
        return self.role in [UserRole.MANAGER, UserRole.ADMIN] or self.is_superuser

    @property
    def is_locked(self):
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False
