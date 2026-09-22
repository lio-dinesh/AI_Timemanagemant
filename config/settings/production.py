import os
from urllib.parse import urlparse
from .base import *

DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'

# Allowed Hosts & CSRF for Cloud Deployments (Render, Vercel, PythonAnywhere, Custom Domains)
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get(
        'DJANGO_ALLOWED_HOSTS',
        '*'
    ).split(',') if h.strip()
]
if '*' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.extend(['.onrender.com', '.vercel.app', '.pythonanywhere.com', 'ai-timemanagemant.vercel.app', 'ai-timemanagemant.onrender.com', 'localhost', '127.0.0.1'])

CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
    'https://*.vercel.app',
    'https://*.pythonanywhere.com',
    'https://ai-timemanagemant.vercel.app',
    'https://ai-timemanagemant.onrender.com',
    'https://ai-timesync-web.onrender.com',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost',
    'http://127.0.0.1',
]
custom_csrf = os.environ.get('CSRF_TRUSTED_ORIGINS')
if custom_csrf:
    CSRF_TRUSTED_ORIGINS.extend([o.strip() for o in custom_csrf.split(',') if o.strip()])


# Database Configuration (Auto-detect DATABASE_URL from Neon, Supabase, Render, Railway)
database_url = os.environ.get('DATABASE_URL')
if database_url:
    try:
        import dj_database_url
        DATABASES = {
            'default': dj_database_url.parse(database_url, conn_max_age=600, ssl_require=True)
        }
    except ImportError:
        parsed_db = urlparse(database_url)
        engine = 'django.db.backends.postgresql'
        if 'mysql' in parsed_db.scheme:
            engine = 'django.db.backends.mysql'

        DATABASES = {
            'default': {
                'ENGINE': engine,
                'NAME': parsed_db.path.lstrip('/'),
                'USER': parsed_db.username or '',
                'PASSWORD': parsed_db.password or '',
                'HOST': parsed_db.hostname or 'localhost',
                'PORT': str(parsed_db.port or (3306 if 'mysql' in engine else 5432)),
            }
        }
        if 'mysql' in engine:
            DATABASES['default']['OPTIONS'] = {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES', innodb_strict_mode=1;",
            }
        else:
            DATABASES['default']['OPTIONS'] = {
                'sslmode': 'require',
            }
else:
    # Build-phase fallback: Use SQLite so collectstatic never attempts a remote database connection
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# WhiteNoise Static Files Serving
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

# Security Headers & Cookies
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

# Reverse Proxy headers - ALWAYS active for Vercel, Render, AWS, Heroku
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True') == 'True'
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Allows frontend forms and HTMX to read and attach the CSRF cookie
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

if SECURE_SSL_REDIRECT:
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Production Cache & Celery (Safe fallback to LocMemCache if Redis not configured)
redis_url = os.environ.get('REDIS_URL')
if redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': redis_url,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

