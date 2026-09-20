from django.urls import path
from apps.ai import views

urlpatterns = [
    path('', views.insights_dashboard, name='ai_insights'),
    path('optimize/', views.trigger_optimizer, name='ai_optimize'),
    path('apply/<int:pk>/', views.apply_insight, name='ai_apply_insight'),
    path('dismiss/<int:pk>/', views.dismiss_insight, name='ai_dismiss_insight'),
    path('nlp/prompt/', views.nlp_command_prompt, name='nlp_command_prompt'),

    # REST APIs
    path('api/insights/', views.api_insights_list, name='api_ai_insights'),
    path('api/nlp/', views.api_nlp_command, name='api_nlp_command'),
    path('api/nlp/command/', views.api_nlp_command, name='api_nlp_command_alias'),
    path('api/nlp/confirm/', views.api_nlp_confirm, name='api_nlp_confirm'),
    path('api/nlp/cancel/', views.api_nlp_cancel, name='api_nlp_cancel'),
    path('api/nlp/evaluate/', views.api_nlp_evaluate, name='api_nlp_evaluate'),
]
