import uuid
from apps.audit.models import AuditLog

SENSITIVE_KEYS = {'password', 'token', 'secret', 'api_key', 'authorization', 'csrfmiddlewaretoken'}

def sanitize_dict(data):
    if not isinstance(data, dict):
        return data
    sanitized = {}
    for k, v in data.items():
        if any(s in k.lower() for s in SENSITIVE_KEYS):
            sanitized[k] = '[REDACTED]'
        elif isinstance(v, dict):
            sanitized[k] = sanitize_dict(v)
        elif isinstance(v, list):
            sanitized[k] = [sanitize_dict(item) if isinstance(item, dict) else item for item in v]
        else:
            sanitized[k] = v
    return sanitized


class AuditService:
    @staticmethod
    def log(action, user=None, resource_type="System", resource_id=None, request=None, status="SUCCESS", reason=None, metadata=None):
        """
        Record a sanitized, structured audit event.
        """
        ip_address = None
        user_agent = None
        request_id = None

        if request:
            # Determine IP address safely
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')

            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            request_id = getattr(request, 'request_id', None) or request.META.get('HTTP_X_REQUEST_ID')

            if user is None and hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user

        sanitized_meta = sanitize_dict(metadata or {})

        try:
            return AuditLog.objects.create(
                user=user,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                reason=reason,
                metadata=sanitized_meta
            )
        except Exception:
            # Audit logging failure should never crash the core business transaction
            return None
