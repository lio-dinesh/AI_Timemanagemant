from django.urls import path
from apps.tracking import views

urlpatterns = [
    path('', views.timer_dashboard, name='timer_dashboard'),
    path('history/', views.time_history, name='time_history'),
    path('start/', views.start_timer, name='start_timer'),
    path('stop/', views.stop_timer, name='stop_timer'),
    path('manual/', views.manual_entry, name='manual_entry'),

    # APIs
    path('api/active/', views.api_active_timer, name='api_active_timer'),
    path('api/start/', views.api_start_timer, name='api_start_timer'),
    path('api/stop/', views.api_stop_timer, name='api_stop_timer'),
]
