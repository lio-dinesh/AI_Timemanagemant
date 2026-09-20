from django.urls import path
from apps.accounts import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signout/', views.logout_view, name='signout'),
    path('accounts/logout/', views.logout_view),
    path('accounts/signout/', views.logout_view),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('team/', views.team_view, name='team'),

    # APIs
    path('api/auth/login/', views.api_login, name='api_login'),
    path('api/users/profile/', views.api_profile, name='api_profile'),
]
