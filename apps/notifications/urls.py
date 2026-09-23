from django.urls import path
from apps.notifications import views

urlpatterns = [
    path('', views.notification_list, name='notification_list'),
    path('<int:pk>/read/', views.mark_as_read, name='mark_as_read'),
    path('read-all/', views.mark_all_as_read, name='mark_all_as_read'),
    path('check-deadlines/', views.trigger_deadline_check, name='trigger_deadline_check'),
    path('analytics/', views.notification_analytics_view, name='notification_analytics'),

    # Brevo Webhook Integration Endpoint
    path('api/integrations/brevo/webhook/', views.brevo_webhook, name='brevo_webhook'),
]
