import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('ai_time_management')

# Load settings using CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscover task modules across all apps
app.autodiscover_tasks()

# Celery Beat Scheduled Tasks
app.conf.beat_schedule = {
    'scan-and-send-due-reminders': {
        'task': 'apps.notifications.tasks.process_due_reminders',
        'schedule': 60.0,  # Run every 60 seconds
    },
    'hourly-anomaly-detection': {
        'task': 'apps.ai.tasks.run_periodic_anomaly_detection',
        'schedule': 3600.0,  # Run every hour
    },
    'daily-summary-aggregation': {
        'task': 'apps.analytics.tasks.run_all_users_daily_aggregation',
        'schedule': crontab(hour=23, minute=50),  # Late evening daily
    },
}
