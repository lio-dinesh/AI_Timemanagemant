import csv
import io
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from apps.accounts.models import User
from apps.projects.models import Project
from apps.tasks.models import Task, TaskStatus
from apps.tracking.models import TimeEntry, TimeEntryStatus
from apps.analytics.models import ProductivityDaily
from apps.notifications.models import Notification, DeliveryStatus
from apps.ai.models import AIInsight

class ReportingService:
    @staticmethod
    def get_user_dashboard_metrics(user):
        """
        Fast dashboard rollup using today's productivity_daily record.
        """
        today = timezone.localdate()
        today_record = ProductivityDaily.objects.filter(user=user, date=today).first()

        # Recent 7 days for trend charts
        past_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        daily_records = list(ProductivityDaily.objects.filter(user=user, date__in=past_7_days).order_by('date'))
        record_map = {r.date: r for r in daily_records}

        trend_labels = [d.strftime('%a %d') for d in past_7_days]
        trend_scores = [record_map[d].productivity_score if d in record_map else 0.0 for d in past_7_days]
        trend_productive_hours = [record_map[d].productive_hours if d in record_map else 0.0 for d in past_7_days]
        trend_tracked_hours = [record_map[d].tracked_hours if d in record_map else 0.0 for d in past_7_days]

        # Tasks overview
        tasks_pending = Task.objects.filter(assigned_to=user, status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]).count()
        tasks_completed = Task.objects.filter(assigned_to=user, status=TaskStatus.COMPLETED).count()
        tasks_overdue = Task.objects.filter(assigned_to=user, deadline__lt=timezone.now(), status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]).count()

        return {
            'today': today_record,
            'today_tracked_hours': today_record.tracked_hours if today_record else 0.0,
            'today_productive_hours': today_record.productive_hours if today_record else 0.0,
            'today_nonproductive_hours': today_record.nonproductive_hours if today_record else 0.0,
            'today_score': today_record.productivity_score if today_record else 0.0,
            'tasks_pending': tasks_pending,
            'tasks_completed': tasks_completed,
            'tasks_overdue': tasks_overdue,
            'trend_labels': trend_labels,
            'trend_scores': trend_scores,
            'trend_productive_hours': trend_productive_hours,
            'trend_tracked_hours': trend_tracked_hours,
        }

    @staticmethod
    def get_manager_dashboard_metrics(manager):
        """
        Rollup for manager team: team members, overall productivity, project progress.
        """
        team_members = list(manager.subordinates.filter(is_active=True))
        member_ids = [m.id for m in team_members]

        today = timezone.localdate()
        team_today_prod = ProductivityDaily.objects.filter(user_id__in=member_ids, date=today).aggregate(
            avg_score=Avg('productivity_score'),
            total_tracked=Sum('tracked_seconds'),
            total_completed=Sum('tasks_completed'),
        )

        team_projects = Project.objects.filter(owner=manager)
        overdue_tasks = Task.objects.filter(assigned_to_id__in=member_ids, deadline__lt=timezone.now(), status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]).count()

        return {
            'team_members': team_members,
            'team_size': len(team_members),
            'avg_team_score': round(team_today_prod['avg_score'] or 0.0, 1),
            'team_tracked_hours': round((team_today_prod['total_tracked'] or 0) / 3600, 1),
            'team_completed_tasks': team_today_prod['total_completed'] or 0,
            'overdue_tasks': overdue_tasks,
            'projects': team_projects,
        }

    @staticmethod
    def get_admin_dashboard_metrics():
        """
        System-wide statistics, active users, email delivery rate, security events.
        """
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        total_tasks = Task.objects.count()
        total_projects = Project.objects.count()

        today = timezone.localdate()
        notifs_today = Notification.objects.filter(created_at__date=today).aggregate(
            total=Count('id'),
            failed=Count('id', filter=Q(delivery_status=DeliveryStatus.FAILED)),
            delivered=Count('id', filter=Q(delivery_status=DeliveryStatus.DELIVERED)),
        )

        from apps.audit.models import AuditLog
        recent_security_events = AuditLog.objects.filter(
            action__in=['LOGIN_FAILED', 'SECURITY_ALERT', 'PERMISSION_DENIED']
        ).order_by('-created_at')[:10]

        return {
            'total_users': total_users,
            'active_users': active_users,
            'total_tasks': total_tasks,
            'total_projects': total_projects,
            'notifs_today': notifs_today,
            'recent_security_events': recent_security_events,
        }

    @staticmethod
    def generate_csv_report(user, start_date, end_date):
        """
        Generates CSV report of productivity summaries for date range.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'Date', 'Tracked Hours', 'Productive Hours', 'Nonproductive Hours',
            'Neutral Hours', 'Focus Hours', 'Meeting Hours', 'Break Hours',
            'Productivity Score (%)', 'Efficiency Score (%)', 'Tasks Completed', 'Tasks Overdue'
        ])

        records = ProductivityDaily.objects.filter(
            user=user,
            date__range=(start_date, end_date)
        ).order_by('date')

        for r in records:
            writer.writerow([
                r.date.strftime('%Y-%m-%d'),
                r.tracked_hours,
                r.productive_hours,
                r.nonproductive_hours,
                round(r.neutral_seconds / 3600, 2),
                round(r.focus_seconds / 3600, 2),
                round(r.meeting_seconds / 3600, 2),
                round(r.break_seconds / 3600, 2),
                r.productivity_score,
                r.efficiency_score,
                r.tasks_completed,
                r.tasks_overdue
            ])

        return output.getvalue()
