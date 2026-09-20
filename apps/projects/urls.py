from django.urls import path
from apps.projects import views

urlpatterns = [
    path('', views.project_list, name='project_list'),
    path('create/', views.project_create, name='project_create'),
    path('<int:pk>/', views.project_detail, name='project_detail'),
    path('<int:pk>/archive/', views.project_archive, name='project_archive'),

    # APIs
    path('api/', views.api_projects_list_create, name='api_projects'),
]
