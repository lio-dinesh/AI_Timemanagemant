import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from apps.tasks.models import Task, TaskStatus
from apps.tasks.forms import TaskForm
from apps.tasks.services.task import TaskService
from apps.projects.models import Project
from apps.audit.services.auditor import AuditService
from apps.notifications.services.engine import NotificationEngine

@login_required
def task_list(request):
    status_filter = request.GET.get('status')
    project_id = request.GET.get('project_id')
    category = request.GET.get('category')

    tasks_qs = TaskService.get_user_tasks(request.user, status=status_filter, project_id=project_id, category=category)

    paginator = Paginator(tasks_qs, 15)
    page_number = request.GET.get('page') or 1
    page_obj = paginator.get_page(page_number)

    projects = Project.objects.all() if request.user.is_admin_role else Project.objects.filter(owner=request.user)

    context = {
        'page_obj': page_obj,
        'projects': projects,
        'selected_status': status_filter,
        'selected_project': project_id,
    }

    # If HTMX request, render partial row/table for seamless live updates
    if request.headers.get('HX-Request') and not request.headers.get('HX-Boosted'):
        return render(request, 'tasks/partials/task_table.html', context)

    return render(request, 'tasks/list.html', context)


@login_required
def task_detail(request, pk):
    tasks = TaskService.get_user_tasks(request.user)
    task = get_object_or_404(tasks, pk=pk)
    time_entries = task.time_entries.order_by('-started_at')[:10]
    return render(request, 'tasks/detail.html', {'task': task, 'time_entries': time_entries})


@login_required
def task_create(request):
    projects_qs = Project.objects.all() if request.user.is_admin_role else Project.objects.filter(owner=request.user)

    if request.method == 'POST':
        form = TaskForm(request.POST)
        form.fields['project'].queryset = projects_qs
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            if not task.assigned_to_id:
                task.assigned_to = request.user
            if not task.status:
                task.status = TaskStatus.TODO
            if task.progress is None:
                task.progress = 0
            if not task.category:
                task.category = 'General'
            if not task.estimated_seconds:
                task.estimated_seconds = 3600
            task.save()
            AuditService.log('TASK_CREATED', request.user, 'Task', task.id, request, 'SUCCESS', metadata={'title': task.title, 'priority': task.priority})
            NotificationEngine.notify_task_assigned(task, assigned_by=request.user)
            messages.success(request, f"Task '{task.title}' created successfully.")
            return redirect('task_detail', pk=task.pk)
        else:
            messages.error(request, "Failed to create task. Please check the highlighted form errors below.")
    else:
        initial = {
            'assigned_to': request.user,
            'status': TaskStatus.TODO,
            'progress': 0,
            'category': 'General',
            'estimated_seconds': 3600
        }
        if request.GET.get('project_id'):
            initial['project'] = request.GET.get('project_id')
        form = TaskForm(initial=initial)
        form.fields['project'].queryset = projects_qs

    return render(request, 'tasks/form.html', {'form': form, 'title': 'Create Task'})


@login_required
@require_POST
def task_toggle_status(request, pk):
    tasks = TaskService.get_user_tasks(request.user)
    task = get_object_or_404(tasks, pk=pk)

    new_status = request.POST.get('status')
    if new_status in TaskStatus.values:
        task.status = new_status
        if new_status == TaskStatus.COMPLETED:
            task.progress = 100
            task.completed_at = timezone.now()
            NotificationEngine.notify_task_completed(task, completed_by=request.user)
        elif new_status == TaskStatus.IN_PROGRESS and not task.started_at:
            task.started_at = timezone.now()
        task.save(update_fields=['status', 'progress', 'completed_at', 'started_at', 'updated_at'])
        AuditService.log('TASK_UPDATED', request.user, 'Task', task.id, request, 'SUCCESS', metadata={'new_status': new_status})

    if request.headers.get('HX-Request'):
        return render(request, 'tasks/partials/task_row.html', {'task': task})

    return redirect('task_detail', pk=task.pk)


# REST API endpoints
@login_required
def api_tasks_list_create(request):
    if request.method == 'GET':
        tasks = TaskService.get_user_tasks(request.user)
        data = [{
            'id': t.id,
            'title': t.title,
            'status': t.status,
            'priority': t.priority,
            'progress': t.progress,
            'deadline': t.deadline.isoformat(),
            'actual_hours': t.actual_hours,
            'estimated_hours': t.estimated_hours,
            'assigned_to_id': t.assigned_to_id
        } for t in tasks[:50]]
        return JsonResponse({'status': 'success', 'tasks': data})

    elif request.method == 'POST':
        try:
            payload = json.loads(request.body)
            raw_deadline = payload.get('deadline')
            deadline = None
            if raw_deadline:
                from django.utils.dateparse import parse_datetime
                parsed_dt = parse_datetime(str(raw_deadline))
                if parsed_dt:
                    deadline = timezone.make_aware(parsed_dt) if timezone.is_naive(parsed_dt) else parsed_dt
            if not deadline:
                deadline = timezone.now() + timezone.timedelta(days=1)

            task = Task.objects.create(
                created_by=request.user,
                assigned_to_id=payload.get('assigned_to_id') or request.user.id,
                project_id=payload.get('project_id'),
                title=payload['title'],
                description=payload.get('description', ''),
                status=payload.get('status', TaskStatus.TODO),
                priority=int(payload.get('priority', 5)),
                progress=int(payload.get('progress', 0)),
                estimated_seconds=int(payload.get('estimated_seconds', 3600)),
                deadline=deadline,
                category=payload.get('category', 'General')
            )
            AuditService.log('TASK_CREATED', request.user, 'Task', task.id, request, 'SUCCESS', metadata={'title': task.title, 'source': 'REST_API'})
            NotificationEngine.notify_task_assigned(task, assigned_by=request.user)
            return JsonResponse({'status': 'success', 'task_id': task.id}, status=201)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
