from django.urls import path
from apps.tasks import views

urlpatterns = [
    path('', views.task_list, name='task_list'),
    path('create/', views.task_create, name='task_create'),
    path('<int:pk>/', views.task_detail, name='task_detail'),
    path('<int:pk>/status/', views.task_toggle_status, name='task_toggle_status'),

    # APIs
    path('api/', views.api_tasks_list_create, name='api_tasks'),
]
