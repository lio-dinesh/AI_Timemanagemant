import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from apps.notifications.models import Notification, NotificationChannel, DeliveryStatus
from apps.notifications.services.engine import NotificationEngine
from apps.notifications.services.brevo import BrevoEmailService

logger = logging.getLogger(__name__)

@login_required
def notification_list(request):
    filter_status = request.GET.get('status')
    notifications = Notification.objects.filter(
        user=request.user,
        channel=NotificationChannel.IN_APP
    ).order_by('-scheduled_for')

    if filter_status == 'unread':
        notifications = notifications.filter(read_at__isnull=True)

    return render(request, 'notifications/list.html', {
        'notifications': notifications[:50],
        'filter_status': filter_status,
    })


@login_required
@require_POST
def mark_as_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.mark_as_read()

    if request.headers.get('HX-Request'):
        return HttpResponse("<span class='badge bg-light text-muted'>Read</span>")
    return redirect('notification_list')


@login_required
@require_POST
def mark_all_as_read(request):
    Notification.objects.filter(
        user=request.user,
        channel=NotificationChannel.IN_APP,
        read_at__isnull=True
    ).update(read_at=timezone.now(), delivery_status=DeliveryStatus.READ)

    messages.success(request, "All notifications marked as read.")
    return redirect('notification_list')


@login_required
def notification_analytics_view(request):
    analytics = NotificationEngine.get_notification_analytics(request.user)
    return render(request, 'notifications/analytics.html', {'analytics': analytics})


# BREVO TRANSACTIONAL EMAIL WEBHOOK (POST /api/integrations/brevo/webhook/)
@csrf_exempt
@require_POST
def brevo_webhook(request):
    """
    Secure endpoint receiving asynchronous delivery status updates from Brevo.
    Token authenticated via Header or Query param. Idempotent processing.
    """
    token = request.headers.get('X-Brevo-Webhook-Token') or request.GET.get('token')
    expected_token = BrevoEmailService.get_webhook_token()

    if expected_token and token != expected_token:
        logger.warning("Unauthorized Brevo webhook attempt with invalid token.")
        return JsonResponse({'status': 'error', 'message': 'Invalid token'}, status=401)

    try:
        payload = json.loads(request.body)
        # Brevo sends single event dict or list of event dicts
        events = payload if isinstance(payload, list) else [payload]

        processed_count = 0
        for ev in events:
            success, msg = BrevoEmailService.process_webhook_event(ev)
            if success:
                processed_count += 1

        return JsonResponse({'status': 'success', 'processed': processed_count})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Malformed JSON'}, status=400)
    except Exception as e:
        logger.error("Error processing Brevo webhook: %s", str(e))
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
