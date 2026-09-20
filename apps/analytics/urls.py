from django.urls import path
from apps.analytics import views

urlpatterns = [
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('reports/', views.reports_view, name='reports'),
    path('reports/csv/', views.export_csv_report, name='export_csv_report'),

    # APIs
    path('api/daily/', views.api_daily_productivity, name='api_daily_productivity'),
]
