import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from apps.projects.models import Project, ProjectStatus
from apps.projects.forms import ProjectForm
from apps.projects.services.project import ProjectService
from apps.audit.services.auditor import AuditService

@login_required
def project_list(request):
    projects = ProjectService.get_user_projects(request.user)
    return render(request, 'projects/list.html', {'projects': projects})


@login_required
def project_detail(request, pk):
    projects = ProjectService.get_user_projects(request.user)
    project = get_object_or_404(projects, pk=pk)
    stats = ProjectService.get_project_statistics(project.id)
    tasks = project.tasks.select_related('assigned_to').order_by('deadline')
    return render(request, 'projects/detail.html', {
        'project': project,
        'stats': stats,
        'tasks': tasks
    })


@login_required
def project_create(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            AuditService.log('TASK_CREATED', request.user, 'Project', project.id, request, 'SUCCESS')
            messages.success(request, f"Project '{project.name}' created.")
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm()
    return render(request, 'projects/form.html', {'form': form, 'title': 'Create Project'})


@login_required
def project_archive(request, pk):
    projects = ProjectService.get_user_projects(request.user)
    project = get_object_or_404(projects, pk=pk)
    project.archive()
    messages.info(request, f"Project '{project.name}' archived.")
    return redirect('project_list')


# REST API endpoints
@login_required
def api_projects_list_create(request):
    if request.method == 'GET':
        projects = ProjectService.get_user_projects(request.user)
        data = [{
            'id': p.id,
            'name': p.name,
            'status': p.status,
            'priority': p.priority,
            'deadline': p.deadline.isoformat(),
            'owner_id': p.owner_id
        } for p in projects]
        return JsonResponse({'status': 'success', 'projects': data})

    elif request.method == 'POST':
        try:
            payload = json.loads(request.body)
            project = Project.objects.create(
                owner=request.user,
                name=payload['name'],
                description=payload.get('description', ''),
                status=payload.get('status', ProjectStatus.ACTIVE),
                priority=int(payload.get('priority', 5)),
                deadline=payload['deadline']
            )
            return JsonResponse({'status': 'success', 'project_id': project.id}, status=201)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
