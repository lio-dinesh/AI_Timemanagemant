from django.urls import path
from apps.audit import views

urlpatterns = [
    path('', views.audit_log_list, name='audit_list'),
]
