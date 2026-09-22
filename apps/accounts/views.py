import json
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from apps.accounts.forms import LoginForm, RegisterForm, ProfileForm
from apps.accounts.services.auth import AuthService
from apps.accounts.models import User, UserRole

def login_view(request):
    try:
        if request.user.is_authenticated:
            return redirect('user_dashboard')
    except Exception:
        # If database tables are not migrated yet, redirect to automatic database setup
        return redirect('setup_database')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user, error_msg = AuthService.authenticate_user(request, email, password)
            if user:
                login(request, user)
                messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
                next_url = request.GET.get('next') or 'user_dashboard'
                return redirect(next_url)
            else:
                messages.error(request, error_msg)
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out securely.")
    return redirect('login')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('user_dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.set_password(form.cleaned_data['password'])
                user.save()
                login(request, user)
                messages.success(request, "Account created successfully!")
                return redirect('user_dashboard')
            except Exception as e:
                messages.error(request, f"Registration error: {str(e)}")
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile_view(request):
    user = request.user
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            # Update preferences JSON if provided
            focus_duration = request.POST.get('preferred_focus_duration')
            break_duration = request.POST.get('break_duration')
            if focus_duration or break_duration:
                prefs = user.preferences or {}
                if focus_duration:
                    prefs['preferred_focus_duration'] = int(focus_duration)
                if break_duration:
                    prefs['break_duration'] = int(break_duration)
                user.preferences = prefs

            # Update notification preferences JSON
            notif_prefs = user.notification_preferences or {}
            notif_prefs['email_enabled'] = request.POST.get('email_enabled') == 'on'
            notif_prefs['in_app_enabled'] = request.POST.get('in_app_enabled') == 'on'
            notif_prefs['task_deadline_reminders'] = request.POST.get('task_deadline_reminders') == 'on'
            notif_prefs['daily_summary'] = request.POST.get('daily_summary') == 'on'
            user.notification_preferences = notif_prefs

            user.save(update_fields=['preferences', 'notification_preferences'])
            messages.success(request, "Profile and preferences updated successfully.")
            return redirect('profile')
    else:
        form = ProfileForm(instance=user)

    return render(request, 'accounts/profile.html', {
        'form': form,
        'user': user,
        'preferences': user.preferences or {},
        'notif_preferences': user.notification_preferences or {}
    })


@login_required
def team_view(request):
    if not request.user.is_manager_role:
        messages.error(request, "Access restricted to Managers and Administrators.")
        return redirect('user_dashboard')

    if request.user.is_admin_role:
        members = User.objects.filter(is_active=True).select_related('manager')
    else:
        members = request.user.subordinates.filter(is_active=True)

    return render(request, 'accounts/team.html', {'members': members})


# REST API endpoints
@require_POST
def api_login(request):
    try:
        data = json.loads(request.body)
        email = data.get('email')
        password = data.get('password')
        user, error = AuthService.authenticate_user(request, email, password)
        if user:
            login(request, user)
            return JsonResponse({'status': 'success', 'user_id': user.id, 'email': user.email, 'role': user.role})
        return JsonResponse({'status': 'error', 'message': error}, status=401)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def api_profile(request):
    user = request.user
    if request.method == 'GET':
        return JsonResponse({
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'role': user.role,
            'timezone': user.timezone,
            'work_start_time': str(user.work_start_time),
            'work_end_time': str(user.work_end_time),
            'preferences': user.preferences,
            'notification_preferences': user.notification_preferences
        })
    elif request.method in ['PUT', 'POST']:
        try:
            data = json.loads(request.body)
            for field in ['first_name', 'last_name', 'timezone']:
                if field in data:
                    setattr(user, field, data[field])
            if 'preferences' in data:
                user.preferences = data['preferences']
            if 'notification_preferences' in data:
                user.notification_preferences = data['notification_preferences']
            user.save()
            return JsonResponse({'status': 'success', 'message': 'Profile updated'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
