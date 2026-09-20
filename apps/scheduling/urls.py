from django.urls import path
from apps.scheduling import views

urlpatterns = [
    path('', views.calendar_view, name='calendar'),
    path('create/', views.create_event, name='create_event'),

    # APIs
    path('api/events/', views.api_schedule_events, name='api_schedule_events'),
    path('api/check-conflict/', views.api_check_conflict, name='api_check_conflict'),
]
