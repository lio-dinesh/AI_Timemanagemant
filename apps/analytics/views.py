import datetime
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from apps.analytics.services.reports import ReportingService
from apps.analytics.services.aggregator import ProductivityAggregator
from apps.analytics.models import ProductivityDaily
from apps.scheduling.services.scheduler import ScheduleService
from apps.ai.models import AIInsight, InsightStatus

@login_required
def user_dashboard(request):
    user = request.user
    today = timezone.localdate()

    # Trigger single-day sync for today to ensure up-to-the-minute numbers
    ProductivityAggregator.aggregate_user_date(user.id, today)

    metrics = ReportingService.get_user_dashboard_metrics(user)

    # Upcoming events for today
    day_start = timezone.make_aware(datetime.datetime.combine(today, datetime.time.min))
    day_end = timezone.make_aware(datetime.datetime.combine(today, datetime.time.max))
    upcoming_events = ScheduleService.get_user_schedule(user, day_start, day_end)

    # Active AI recommendations
    ai_recommendations = AIInsight.objects.filter(user=user, status=InsightStatus.ACTIVE)[:3]

    return render(request, 'dashboard/user_dashboard.html', {
        'metrics': metrics,
        'upcoming_events': upcoming_events,
        'ai_recommendations': ai_recommendations,
    })


@login_required
def manager_dashboard(request):
    if not request.user.is_manager_role:
        messages.error(request, "Access restricted to Managers and Administrators.")
        return redirect('user_dashboard')

    metrics = ReportingService.get_manager_dashboard_metrics(request.user)
    return render(request, 'dashboard/manager_dashboard.html', {'metrics': metrics})


@login_required
def admin_dashboard(request):
    if not request.user.is_admin_role:
        messages.error(request, "Access restricted to Administrators.")
        return redirect('user_dashboard')

    metrics = ReportingService.get_admin_dashboard_metrics()
    return render(request, 'dashboard/admin_dashboard.html', {'metrics': metrics})


@login_required
def reports_view(request):
    user = request.user
    today = timezone.localdate()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str and end_date_str:
        try:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today - datetime.timedelta(days=7)
            end_date = today
    else:
        start_date = today - datetime.timedelta(days=7)
        end_date = today

    records = ProductivityDaily.objects.filter(
        user=user,
        date__range=(start_date, end_date)
    ).order_by('date')

    return render(request, 'analytics/reports.html', {
        'records': records,
        'start_date': start_date,
        'end_date': end_date,
    })


@login_required
def export_csv_report(request):
    user = request.user
    today = timezone.localdate()
    start_date = today - datetime.timedelta(days=30)
    end_date = today

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    if start_date_str and end_date_str:
        try:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    csv_data = ReportingService.generate_csv_report(user, start_date, end_date)
    response = HttpResponse(csv_data, content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="productivity_report_{start_date}_{end_date}.csv"'
    return response


# REST API
@login_required
def api_daily_productivity(request):
    days = int(request.GET.get('days', 14))
    start_date = timezone.localdate() - datetime.timedelta(days=days)
    records = ProductivityDaily.objects.filter(user=request.user, date__gte=start_date).order_by('date')
    data = [{
        'date': r.date.isoformat(),
        'tracked_hours': r.tracked_hours,
        'productive_hours': r.productive_hours,
        'score': r.productivity_score,
        'completion_rate': r.completion_rate
    } for r in records]
    return JsonResponse({'status': 'success', 'history': data})
