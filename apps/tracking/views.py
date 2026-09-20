import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from apps.tracking.models import TimeEntry, TimeEntryStatus
from apps.tracking.services.timer import TimerService, TimerConflictError, TimerNotFoundError
from apps.tracking.forms import ManualTimeEntryForm
from apps.tasks.models import Task, TaskStatus

@login_required
def timer_dashboard(request):
    active_timer = TimerService.get_active_timer(request.user)
    recent_tasks = Task.objects.filter(assigned_to=request.user, status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS])
    return render(request, 'tracking/timer.html', {
        'active_timer': active_timer,
        'recent_tasks': recent_tasks
    })


@login_required
def time_history(request):
    entries_qs = TimeEntry.objects.filter(user=request.user).select_related('task', 'project').order_by('-started_at')

    # Date filtering
    date_filter = request.GET.get('date')
    if date_filter:
        entries_qs = entries_qs.filter(started_at__date=date_filter)

    paginator = Paginator(entries_qs, 20)
    page_number = request.GET.get('page') or 1
    page_obj = paginator.get_page(page_number)

    return render(request, 'tracking/history.html', {
        'page_obj': page_obj,
        'selected_date': date_filter
    })


@login_required
@require_POST
def start_timer(request):
    task_id = request.POST.get('task_id') or None
    activity_type = request.POST.get('activity_type') or "General Work"
    notes = request.POST.get('notes') or ""

    try:
        entry = TimerService.start_timer(
            user=request.user,
            task_id=task_id,
            activity_type=activity_type,
            notes=notes,
            request=request
        )
        if request.headers.get('HX-Request'):
            return render(request, 'components/timer_widget.html', {'active_timer': entry})
        messages.success(request, "Timer started successfully.")
        return redirect('timer_dashboard')
    except TimerConflictError as err:
        if request.headers.get('HX-Request'):
            return HttpResponse(f"<div class='alert alert-warning py-1 my-1 small'>{str(err)}</div>", status=400)
        messages.warning(request, str(err))
        return redirect('timer_dashboard')
    except Exception as err:
        if request.headers.get('HX-Request'):
            return HttpResponse(f"<div class='alert alert-danger py-1 my-1 small'>{str(err)}</div>", status=400)
        messages.error(request, str(err))
        return redirect('timer_dashboard')


@login_required
@require_POST
def stop_timer(request):
    idle_seconds = request.POST.get('idle_seconds') or 0
    notes = request.POST.get('notes') or None

    try:
        entry = TimerService.stop_timer(
            user=request.user,
            idle_seconds=int(idle_seconds),
            notes=notes,
            request=request
        )
        if request.headers.get('HX-Request'):
            return render(request, 'components/timer_widget.html', {'active_timer': None})
        messages.success(request, f"Timer stopped. Total duration: {entry.formatted_duration}")
        return redirect('timer_dashboard')
    except TimerNotFoundError as err:
        if request.headers.get('HX-Request'):
            return render(request, 'components/timer_widget.html', {'active_timer': None})
        messages.info(request, str(err))
        return redirect('timer_dashboard')
    except Exception as err:
        messages.error(request, str(err))
        return redirect('timer_dashboard')


@login_required
def manual_entry(request):
    tasks = Task.objects.filter(assigned_to=request.user)
    if request.method == 'POST':
        form = ManualTimeEntryForm(request.POST)
        if form.is_valid():
            try:
                entry = TimerService.create_manual_entry(
                    user=request.user,
                    start_time=form.cleaned_data['start_time'],
                    end_time=form.cleaned_data['end_time'],
                    task_id=form.cleaned_data.get('task_id') or None,
                    activity_type=form.cleaned_data['activity_type'],
                    category=form.cleaned_data['productivity_category'],
                    idle_seconds=form.cleaned_data['idle_seconds'],
                    notes=form.cleaned_data.get('notes'),
                    request=request
                )
                messages.success(request, f"Manual time entry ({entry.formatted_duration}) saved.")
                return redirect('time_history')
            except Exception as e:
                messages.error(request, f"Error saving time entry: {str(e)}")
    else:
        form = ManualTimeEntryForm()

    return render(request, 'tracking/manual_entry.html', {'form': form, 'tasks': tasks})


# REST APIs
@login_required
def api_active_timer(request):
    entry = TimerService.get_active_timer(request.user)
    if entry:
        return JsonResponse({
            'status': 'active',
            'session_uuid': str(entry.session_uuid),
            'started_at': entry.started_at.isoformat(),
            'task_id': entry.task_id,
            'task_title': entry.task.title if entry.task else None,
            'activity_type': entry.activity_type,
            'category': entry.productivity_category
        })
    return JsonResponse({'status': 'idle'})


@login_required
@require_POST
def api_start_timer(request):
    try:
        data = json.loads(request.body) if request.body else {}
        entry = TimerService.start_timer(
            user=request.user,
            task_id=data.get('task_id'),
            activity_type=data.get('activity_type', 'General Work'),
            notes=data.get('notes'),
            request=request
        )
        return JsonResponse({
            'status': 'success',
            'session_uuid': str(entry.session_uuid),
            'started_at': entry.started_at.isoformat()
        }, status=201)
    except TimerConflictError as e:
        return JsonResponse({'status': 'conflict', 'message': str(e)}, status=409)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_POST
def api_stop_timer(request):
    try:
        data = json.loads(request.body) if request.body else {}
        entry = TimerService.stop_timer(
            user=request.user,
            session_uuid=data.get('session_uuid'),
            idle_seconds=data.get('idle_seconds', 0),
            notes=data.get('notes'),
            request=request
        )
        return JsonResponse({
            'status': 'success',
            'duration_seconds': entry.duration_seconds,
            'active_seconds': entry.active_seconds,
            'idle_seconds': entry.idle_seconds
        })
    except TimerNotFoundError as e:
        return JsonResponse({'status': 'not_found', 'message': str(e)}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
