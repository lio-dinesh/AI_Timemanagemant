from django.db import models
from django.conf import settings

class AuditAction(models.TextChoices):
    LOGIN_SUCCESS = 'LOGIN_SUCCESS', 'Login Success'
    LOGIN_FAILED = 'LOGIN_FAILED', 'Login Failed'
    LOGOUT = 'LOGOUT', 'Logout'
    PASSWORD_CHANGED = 'PASSWORD_CHANGED', 'Password Changed'
    PASSWORD_RESET = 'PASSWORD_RESET', 'Password Reset'
    PROFILE_UPDATED = 'PROFILE_UPDATED', 'Profile Updated'
    TASK_CREATED = 'TASK_CREATED', 'Task Created'
    TASK_UPDATED = 'TASK_UPDATED', 'Task Updated'
    TASK_DELETED = 'TASK_DELETED', 'Task Deleted'
    TASK_ASSIGNED = 'TASK_ASSIGNED', 'Task Assigned'
    TIME_STARTED = 'TIME_STARTED', 'Time Started'
    TIME_STOPPED = 'TIME_STOPPED', 'Time Stopped'
    SCHEDULE_CREATED = 'SCHEDULE_CREATED', 'Schedule Created'
    SCHEDULE_CHANGED = 'SCHEDULE_CHANGED', 'Schedule Changed'
    AI_ACTION_ACCEPTED = 'AI_ACTION_ACCEPTED', 'AI Action Accepted'
    AI_ACTION_REJECTED = 'AI_ACTION_REJECTED', 'AI Action Rejected'
    NOTIFICATION_SENT = 'NOTIFICATION_SENT', 'Notification Sent'
    SECURITY_ALERT = 'SECURITY_ALERT', 'Security Alert'
    PERMISSION_DENIED = 'PERMISSION_DENIED', 'Permission Denied'


class AuditStatus(models.TextChoices):
    SUCCESS = 'SUCCESS', 'Success'
    FAILED = 'FAILED', 'Failed'


class AuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=50, db_index=True)
    resource_type = models.CharField(max_length=64, db_index=True)
    resource_id = models.CharField(max_length=64, null=True, blank=True)
    request_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=AuditStatus.choices, default=AuditStatus.SUCCESS)
    reason = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['resource_type', 'resource_id']),
        ]

    def __str__(self):
        user_str = self.user.email if self.user else "Anonymous"
        return f"[{self.created_at:%Y-%m-%d %H:%M:%S}] {self.action} by {user_str} ({self.status})"
