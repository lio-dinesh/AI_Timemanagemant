from django.core.cache import cache
from apps.notifications.models import Notification, NotificationChannel

def unread_notifications_context(request):
    if request.user.is_authenticated:
        cache_key = f"user_{request.user.id}_notif_ctx"
        cached_val = cache.get(cache_key)
        if cached_val is not None:
            return cached_val

        unread_count = Notification.objects.filter(
            user=request.user,
            channel=NotificationChannel.IN_APP,
            read_at__isnull=True
        ).count()
        recent_notifications = list(Notification.objects.filter(
            user=request.user,
            channel=NotificationChannel.IN_APP
        ).order_by('-scheduled_for')[:5])

        result = {
            'unread_notifications_count': unread_count,
            'recent_notifications': recent_notifications,
        }
        cache.set(cache_key, result, timeout=3)
        return result

    return {
        'unread_notifications_count': 0,
        'recent_notifications': [],
    }
