import json
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from apps.scheduling.models import ScheduleEvent, ScheduleEventType, ScheduleEventStatus
from apps.scheduling.forms import ScheduleEventForm
from apps.scheduling.services.scheduler import ScheduleService, ConflictError

@login_required
def calendar_view(request):
    now = timezone.now()
    # Default range: current week (Monday to Sunday)
    start_week = now - datetime.timedelta(days=now.weekday())
    end_week = start_week + datetime.timedelta(days=7)

    events = ScheduleService.get_user_schedule(request.user, start_week, end_week)
    return render(request, 'scheduling/calendar.html', {
        'events': events,
        'start_week': start_week,
        'end_week': end_week,
    })


@login_required
def create_event(request):
    if request.method == 'POST':
        form = ScheduleEventForm(request.POST)
        if form.is_valid():
            try:
                event = ScheduleService.create_event(
                    user=request.user,
                    title=form.cleaned_data['title'],
                    start_at=form.cleaned_data['start_at'],
                    end_at=form.cleaned_data['end_at'],
                    event_type=form.cleaned_data['event_type'],
                    task_id=form.cleaned_data.get('task').id if form.cleaned_data.get('task') else None,
                    description=form.cleaned_data.get('description', ''),
                    location=form.cleaned_data.get('location', ''),
                    meeting_url=form.cleaned_data.get('meeting_url', ''),
                    reminder_minutes=form.cleaned_data.get('reminder_minutes', 15)
                )
                messages.success(request, f"Event '{event.title}' scheduled.")
                return redirect('calendar')
            except ConflictError as err:
                messages.warning(request, str(err))
            except Exception as err:
                messages.error(request, str(err))
    else:
        form = ScheduleEventForm()

    return render(request, 'scheduling/form.html', {'form': form, 'title': 'Schedule Event'})


# REST APIs
@login_required
def api_schedule_events(request):
    start = request.GET.get('start') or (timezone.now() - datetime.timedelta(days=7)).isoformat()
    end = request.GET.get('end') or (timezone.now() + datetime.timedelta(days=14)).isoformat()

    events = ScheduleService.get_user_schedule(request.user, start, end)
    data = [{
        'id': e.id,
        'title': e.title,
        'event_type': e.event_type,
        'start': e.start_at.isoformat(),
        'end': e.end_at.isoformat(),
        'status': e.status,
        'location': e.location,
        'meeting_url': e.meeting_url
    } for e in events]
    return JsonResponse({'status': 'success', 'events': data})


@login_required
def api_check_conflict(request):
    try:
        data = json.loads(request.body)
        start = datetime.datetime.fromisoformat(data['start_at'])
        end = datetime.datetime.fromisoformat(data['end_at'])
        conflicts = ScheduleService.detect_conflicts(request.user, start, end)
        return JsonResponse({
            'has_conflict': len(conflicts) > 0,
            'conflicts': [{'id': c.id, 'title': c.title, 'start': c.start_at.isoformat(), 'end': c.end_at.isoformat()} for c in conflicts]
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
