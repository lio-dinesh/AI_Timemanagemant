from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from apps.audit.models import AuditLog

@login_required
def audit_log_list(request):
    if not request.user.is_admin_role:
        messages.error(request, "Access restricted to Administrators.")
        return redirect('user_dashboard')

    logs_qs = AuditLog.objects.select_related('user').order_by('-created_at')

    action_filter = request.GET.get('action')
    status_filter = request.GET.get('status')
    if action_filter:
        logs_qs = logs_qs.filter(action=action_filter)
    if status_filter:
        logs_qs = logs_qs.filter(status=status_filter)

    paginator = Paginator(logs_qs, 25)
    page_number = request.GET.get('page') or 1
    page_obj = paginator.get_page(page_number)

    return render(request, 'audit/list.html', {
        'page_obj': page_obj,
        'action_filter': action_filter,
        'status_filter': status_filter,
    })
