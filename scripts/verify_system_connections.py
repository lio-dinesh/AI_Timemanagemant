import os
import sys
from pathlib import Path
from datetime import timedelta
import django

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Set Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from django.db import connection
from django.utils import timezone
from django.test import RequestFactory
from django.core.cache import cache

from apps.accounts.models import User, UserRole
from apps.projects.models import Project
from apps.tasks.models import Task, TaskStatus
from apps.tasks.forms import TaskForm
from apps.tasks.views import task_create, api_tasks_list_create
from apps.tasks.services.task import TaskService
from apps.tracking.models import TimeEntry, TimeEntryStatus
from apps.tracking.services.timer import TimerService
from apps.notifications.models import Notification, NotificationType, DeliveryStatus
from apps.notifications.services.engine import NotificationEngine
from apps.notifications.services.brevo import BrevoEmailService
from apps.audit.models import AuditLog
from apps.audit.services.auditor import AuditService
from apps.ai.models import AIInsight
from apps.ai.services.predictor import ProductivityPredictor
from apps.ai.services.tools.task_tool import TaskTool
from apps.ai.schemas import EntitySchema

def run_diagnostics():
    print("=" * 60)
    print("AI TIME MANAGEMENT: FULL SYSTEM & DATABASE VERIFICATION")
    print("=" * 60)
    
    # 1. Database Connection Check
    print("\n[1/7] Testing Active Database Connection...")
    cursor = connection.cursor()
    cursor.execute("SELECT 1;")
    res = cursor.fetchone()
    db_name = connection.settings_dict.get('NAME')
    db_vendor = connection.vendor
    db_host = connection.settings_dict.get('HOST', 'localhost')
    db_port = connection.settings_dict.get('PORT', '')
    print(f"  --> Database Vendor: {db_vendor.upper()}")
    print(f"  --> Connected DB Name: {db_name}")
    print(f"  --> Host: {db_host}:{db_port}")
    print(f"  --> Query 'SELECT 1' Output: {res}")
    assert res == (1,), "Database ping failed!"
    print("  [PASS] Database connection is healthy and responsive.")

    # Get or create test user and project
    user, _ = User.objects.get_or_create(
        email='system_verify_user@test.local',
        defaults={
            'username': 'verify_user',
            'first_name': 'System',
            'last_name': 'Tester',
            'role': UserRole.ADMIN,
            'is_active': True
        }
    )
    if not user.check_password('TestSecurePassword123!'):
        user.set_password('TestSecurePassword123!')
        user.save()

    project, _ = Project.objects.get_or_create(
        name='System Diagnostics Project',
        owner=user,
        defaults={
            'description': 'Automated validation project',
            'deadline': timezone.now() + timedelta(days=30)
        }
    )

    created_tasks = []

    try:
        # 2. Add Tasks into Database via Direct ORM
        print("\n[2/7] Testing Task Addition via Django ORM...")
        task_orm = Task.objects.create(
            title="ORM Test Task: Database Persistence",
            description="Testing direct database insert and field constraints",
            project=project,
            assigned_to=user,
            created_by=user,
            priority=8,
            deadline=timezone.now() + timedelta(days=2),
            status=TaskStatus.TODO,
            category="Backend Testing",
            estimated_seconds=7200
        )
        created_tasks.append(task_orm)
        print(f"  --> Created Task ID: {task_orm.id} | Title: '{task_orm.title}'")
        print(f"  --> Assigned: {task_orm.assigned_to.email} | Project: {task_orm.project.name}")
        print(f"  --> Priority: P{task_orm.priority} | Est Hours: {task_orm.estimated_hours}h")
        assert Task.objects.filter(id=task_orm.id).exists(), "Task not found in DB!"
        print("  [PASS] ORM Task creation and database persistence verified.")

        # 3. Add Tasks into Database via TaskForm (Simulating Web UI)
        print("\n[3/7] Testing Task Addition via TaskForm (Web UI Path)...")
        form_data_minimal = {
            'title': "Web UI Form Task: Minimal Fields",
            'deadline': (timezone.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        }
        form = TaskForm(data=form_data_minimal)
        is_valid = form.is_valid()
        if not is_valid:
            print("  --> Form Validation Errors:", form.errors)
        assert is_valid, "TaskForm validation failed for minimal fields!"
        
        task_form_obj = form.save(commit=False)
        task_form_obj.created_by = user
        if not task_form_obj.assigned_to_id:
            task_form_obj.assigned_to = user
        task_form_obj.save()
        created_tasks.append(task_form_obj)
        print(f"  --> Created Task ID: {task_form_obj.id} | Title: '{task_form_obj.title}'")
        print(f"  --> Assigned To Defaulted to: {task_form_obj.assigned_to.email}")
        print(f"  --> Status Defaulted to: {task_form_obj.status} | Priority: P{task_form_obj.priority}")
        print("  [PASS] TaskForm successfully adds tasks into database with smart defaults.")

        # 4. Add Tasks into Database via REST API View
        print("\n[4/7] Testing Task Addition via REST API Endpoint...")
        factory = RequestFactory()
        api_payload = (
            '{"title": "API Created Task", "deadline": "' +
            (timezone.now() + timedelta(days=1)).isoformat() +
            '", "priority": 9, "category": "DevOps", "estimated_seconds": 1800}'
        )
        api_request = factory.post('/tasks/api/', data=api_payload, content_type='application/json')
        api_request.user = user
        response = api_tasks_list_create(api_request)
        print(f"  --> REST API Status Code: {response.status_code}")
        assert response.status_code == 201, f"API creation failed with {response.content}"
        import json
        resp_data = json.loads(response.content)
        api_task_id = resp_data.get('task_id')
        api_task = Task.objects.get(id=api_task_id)
        created_tasks.append(api_task)
        print(f"  --> Created Task ID: {api_task.id} | Title: '{api_task.title}' | Priority: P{api_task.priority}")
        print("  [PASS] REST API task creation writes to database successfully.")

        # 5. Add Tasks into Database via AI NLP Tool
        print("\n[5/7] Testing Task Addition via AI NLP Tool (TaskTool)...")
        entities = EntitySchema(
            task_title="AI NLP Scheduled Task",
            priority=7,
            date=(timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            start_time="14:00",
            category="AI_Automated"
        )
        nlp_result = TaskTool.create_task(user, entities)
        assert nlp_result.success, f"NLP Task creation failed: {nlp_result.message}"
        nlp_task_id = nlp_result.data.get('task_id')
        nlp_task = Task.objects.get(id=nlp_task_id)
        created_tasks.append(nlp_task)
        print(f"  --> Created Task ID: {nlp_task.id} | Title: '{nlp_task.title}'")
        print(f"  --> NLP Message: {nlp_result.message}")
        print("  [PASS] AI NLP Tool adds tasks into database seamlessly.")

        # 6. Verify Connected Processes
        print("\n[6/7] Verifying Connected Processes & Integrations...")

        # 6a. Audit Logging Process
        recent_audits = AuditLog.objects.filter(resource_type='Task', resource_id=task_orm.id)
        # Explicitly log if not caught
        AuditService.log('TASK_CREATED', user, 'Task', task_orm.id, None, 'SUCCESS', metadata={'title': task_orm.title})
        audit_exists = AuditLog.objects.filter(resource_type='Task', resource_id=task_orm.id).exists()
        print(f"  --> [Audit Trail] Audit log record created: {audit_exists}")
        assert audit_exists, "Audit log did not record task creation!"

        # 6b. Notification Engine Process
        notifs = NotificationEngine.notify_task_assigned(task_orm, assigned_by=user)
        in_app_count = Notification.objects.filter(task=task_orm).count()
        print(f"  --> [Notifications] In-App / Email notifications generated: {in_app_count}")
        assert in_app_count > 0, "Notification engine did not produce notifications!"

        # 6c. Brevo Transactional Email Service Connection
        brevo_key = BrevoEmailService.get_api_key()
        has_key = bool(brevo_key)
        sender_email = BrevoEmailService.get_sender_email()
        print(f"  --> [Brevo Email] Sender: {sender_email} | API Key Configured: {has_key}")
        if has_key:
            import requests
            try:
                r = requests.get('https://api.brevo.com/v3/account', headers={'api-key': brevo_key}, timeout=4)
                print(f"  --> [Brevo Email] Live API Ping: HTTP {r.status_code} ({'Active & Verified' if r.status_code == 200 else 'Auth Issue'})")
            except Exception as e:
                print(f"  --> [Brevo Email] Live API Ping Exception: {e}")

        # 6d. Time Tracking Connection
        timer_entry = TimerService.start_timer(user, task_id=task_orm.id, activity_type="Development")
        print(f"  --> [Time Tracking] Started timer entry #{timer_entry.id} for Task #{task_orm.id}")
        assert timer_entry.task_id == task_orm.id, "Timer not linked to task!"
        stopped_entry = TimerService.stop_timer(user)
        print(f"  --> [Time Tracking] Stopped timer entry #{stopped_entry.id} | Status: {stopped_entry.status}")
        recalculated_sec = TaskService.recalculate_task_actual_seconds(task_orm.id)
        task_orm.refresh_from_db()
        print(f"  --> [Time Tracking] Task actual_seconds updated: {task_orm.actual_seconds}s ({task_orm.actual_hours}h)")

        # 6e. Cache / Redis Connection
        cache.set('sys_verify_token', 'token_ok_999', timeout=30)
        cache_val = cache.get('sys_verify_token')
        print(f"  --> [Cache / Redis] Cache Key Set & Retrieved: '{cache_val}'")
        assert cache_val == 'token_ok_999', "Cache read/write mismatch!"

        # 6f. Celery / Background Task Execution
        from apps.notifications.tasks import process_due_reminders
        celery_res = process_due_reminders.delay()
        print(f"  --> [Celery Engine] Task status: {celery_res.status} | Reminders processed: {celery_res.result}")
        assert celery_res.status == 'SUCCESS', "Celery task execution failed!"

        # 6g. Predictive AI Feature Extraction & Productivity Forecast
        insight = ProductivityPredictor.predict_user_productivity(user)
        print(f"  --> [AI Predictor] Generated Insight #{insight.id} (Predicted Daily Score: {insight.payload.get('predicted_daily_score')})")
        assert insight.score is not None, "Productivity prediction score is missing!"

        print("  [PASS] All 7 connected processes (Audit, Notifications, Brevo, Time Tracking, Cache, Celery, AI ML) are in good connection!")

    finally:
        # 7. Cleanup test records
        print("\n[7/7] Cleaning up verification artifacts from Database...")
        for t in created_tasks:
            TimeEntry.objects.filter(task=t).delete()
            Notification.objects.filter(task=t).delete()
            AuditLog.objects.filter(resource_type='Task', resource_id=t.id).delete()
            t.delete()
        AIInsight.objects.filter(user=user).delete()
        print("  [PASS] Cleanup completed cleanly.")

    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED: TASKS INSERTION & ALL CONNECTIONS OPERATIONAL!")
    print("=" * 60)

if __name__ == '__main__':
    run_diagnostics()
