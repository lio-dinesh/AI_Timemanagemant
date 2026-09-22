import io
import traceback
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, JsonResponse
from django.db import connection
from django.core.management import call_command

def root_redirect(request):
    try:
        if request.user.is_authenticated:
            return redirect('user_dashboard')
    except Exception:
        return redirect('setup_database')
    return redirect('login')

def setup_database_view(request):
    """
    Applies migrations and seeds demo data on serverless/cloud environments (e.g. Vercel, Neon).
    """
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        html = """
        <!DOCTYPE html>
        <html>
        <head>
          <title>Action Required: Add DATABASE_URL - AI TimeSync</title>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px 20px; line-height: 1.6; }
            .container { max-width: 760px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 36px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            h2 { color: #f59e0b; margin-top: 0; }
            .step { background: #0f172a; padding: 20px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #4f46e5; }
            code { background: #334155; padding: 3px 8px; border-radius: 4px; color: #38bdf8; font-family: monospace; font-size: 13px; }
            ol { margin: 8px 0 0 20px; padding: 0; }
            li { margin-bottom: 6px; }
            .badge { display: inline-block; background: #4f46e5; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; margin-bottom: 8px; }
          </style>
        </head>
        <body>
          <div class="container">
            <h2>⚠️ Database Not Connected: Add DATABASE_URL</h2>
            <p>Your web app is live, but your <b>Neon PostgreSQL</b> connection string has not been added to your hosting environment variables yet.</p>
            
            <div class="step">
              <span class="badge">Render Setup (ai-timemanagemant.onrender.com)</span>
              <ol>
                <li>Open your <b>Render Dashboard</b> &rarr; Click your <b>ai-timesync-web</b> service.</li>
                <li>In the left sidebar, click <b>Environment</b>.</li>
                <li>Click <b>Add Environment Variable</b>.</li>
                <li>Key: <code>DATABASE_URL</code></li>
                <li>Value: Paste your Neon PostgreSQL connection string (e.g. <code>postgresql://neondb_owner:password@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require</code>).</li>
                <li>Click <b>Save Changes</b>. Render will automatically apply migrations and restart the app!</li>
              </ol>
            </div>

            <div class="step">
              <span class="badge" style="background: #0ea5e9;">Vercel Setup (ai-timemanagemant.vercel.app)</span>
              <ol>
                <li>Open your <b>Vercel Dashboard</b> &rarr; Click your <b>ai-timemanagemant</b> project.</li>
                <li>Click <b>Settings</b> &rarr; <b>Environment Variables</b>.</li>
                <li>Add Key: <code>DATABASE_URL</code> &rarr; Value: Your Neon PostgreSQL URL &rarr; Click <b>Save</b>.</li>
                <li>Go to <b>Deployments</b> &rarr; Click <b>...</b> on your latest deployment &rarr; <b>Redeploy</b>.</li>
                <li>Revisit <code>/setup-database/</code> to initialize all database tables!</li>
              </ol>
            </div>
          </div>
        </body>
        </html>
        """
        return HttpResponse(html)

    out = io.StringIO()
    try:
        call_command('migrate', interactive=False, stdout=out)
        call_command('seed_data', stdout=out)
        output_text = out.getvalue()
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <title>Database Setup - AI TimeSync</title>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px 20px; }}
            .container {{ max-width: 720px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
            h2 {{ color: #4ade80; margin-top: 0; }}
            pre {{ background: #0f172a; color: #94a3b8; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 13px; max-height: 350px; line-height: 1.5; }}
            .btn {{ display: inline-block; background: #4f46e5; color: white; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: 600; margin-top: 16px; }}
            .btn:hover {{ background: #4338ca; }}
          </style>
        </head>
        <body>
          <div class="container">
            <h2> Database Migrations & Seeding Successful!</h2>
            <p>All database tables have been created on your Neon database, and initial demonstration accounts are ready.</p>
            <pre>{output_text}</pre>
            <a href="/login/" class="btn">Proceed to Sign In &rarr;</a>
          </div>
        </body>
        </html>
        """
        return HttpResponse(html)
    except Exception:
        err_trace = traceback.format_exc()
        db_conf = settings.DATABASES.get('default', {})
        safe_engine = db_conf.get('ENGINE', 'unknown')
        safe_host = db_conf.get('HOST', 'unknown')
        safe_user = db_conf.get('USER', 'unknown')
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <title>Database Setup Error - AI TimeSync</title>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px 20px; }}
            .container {{ max-width: 720px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
            h2 {{ color: #f87171; margin-top: 0; }}
            pre {{ background: #0f172a; color: #fca5a5; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 13px; }}
            .info {{ background: #334155; padding: 12px; border-radius: 6px; font-size: 13px; color: #cbd5e1; margin-bottom: 16px; }}
          </style>
        </head>
        <body>
          <div class="container">
            <h2>⚠️ Database Setup Failed</h2>
            <p>Django could not run migrations against your database. Check your DATABASE_URL environment variable:</p>
            <div class="info">
              <strong>Database Engine:</strong> {safe_engine}<br>
              <strong>Host:</strong> {safe_host}<br>
              <strong>User:</strong> {safe_user}
            </div>
            <pre>{err_trace}</pre>
          </div>
        </body>
        </html>
        """
        return HttpResponse(html, status=500)

def health_check_view(request):
    """
    Diagnostics endpoint to verify database connectivity.
    """
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        return JsonResponse({
            "status": "warning",
            "message": "DATABASE_URL is not set. Please configure DATABASE_URL in your hosting dashboard with your Neon PostgreSQL URL."
        }, status=200)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"status": "ok", "database": "connected", "host": settings.DATABASES['default'].get('HOST')})
    except Exception as e:
        return JsonResponse({"status": "error", "database": f"error: {str(e)}"}, status=500)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', root_redirect, name='root'),
    path('setup-database/', setup_database_view, name='setup_database'),
    path('health/', health_check_view, name='health_check'),

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
