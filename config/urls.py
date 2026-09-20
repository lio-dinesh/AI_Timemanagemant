from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('user_dashboard')
    return redirect('login')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', root_redirect, name='root'),

    # Core Application Routes
    path('', include('apps.accounts.urls')),
    path('projects/', include('apps.projects.urls')),
    path('tasks/', include('apps.tasks.urls')),
    path('time/', include('apps.tracking.urls')),
    path('schedule/', include('apps.scheduling.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('ai/', include('apps.ai.urls')),
    path('audit/', include('apps.audit.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
