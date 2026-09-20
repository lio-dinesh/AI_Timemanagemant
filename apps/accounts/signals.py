from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from apps.audit.services.auditor import AuditService

@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    AuditService.log(
        action='LOGIN_SUCCESS',
        user=user,
        resource_type='User',
        resource_id=user.id,
        request=request,
        status='SUCCESS'
    )

@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    if user:
        AuditService.log(
            action='LOGOUT',
            user=user,
            resource_type='User',
            resource_id=user.id,
            request=request,
            status='SUCCESS'
        )

@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    AuditService.log(
        action='LOGIN_FAILED',
        user=None,
        resource_type='User',
        resource_id=None,
        request=request,
        status='FAILED',
        reason='Bad credentials',
        metadata={'attempted_email': credentials.get('username') if credentials else None}
    )
