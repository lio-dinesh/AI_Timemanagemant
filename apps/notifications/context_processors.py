from apps.notifications.models import Notification, NotificationChannel, DeliveryStatus

def unread_notifications_context(request):
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            user=request.user,
            channel=NotificationChannel.IN_APP,
            read_at__isnull=True
        ).count()
        recent_notifications = Notification.objects.filter(
            user=request.user,
            channel=NotificationChannel.IN_APP
        ).order_by('-scheduled_for')[:5]
        return {
            'unread_notifications_count': unread_count,
            'recent_notifications': recent_notifications,
        }
    return {
        'unread_notifications_count': 0,
        'recent_notifications': [],
    }
