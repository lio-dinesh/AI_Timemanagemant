from django.urls import path
from apps.scheduling import views

urlpatterns = [
    path('', views.calendar_view, name='calendar'),
    path('create/', views.create_event, name='create_event'),
    path('export/ics/', views.export_calendar_ics, name='export_calendar_ics'),

    # APIs
    path('api/events/', views.api_schedule_events, name='api_schedule_events'),
    path('api/events/<int:event_id>/links/', views.api_event_calendar_links, name='api_event_calendar_links'),
    path('api/check-conflict/', views.api_check_conflict, name='api_check_conflict'),
]
