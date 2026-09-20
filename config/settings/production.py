import os
from urllib.parse import urlparse
from .base import *

DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'

# Allowed Hosts & CSRF for Cloud Deployments (Render, Vercel, PythonAnywhere, Custom Domains)
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get(
        'DJANGO_ALLOWED_HOSTS',
        'localhost,127.0.0.1,.onrender.com,.vercel.app,.pythonanywhere.com'
    ).split(',') if h.strip()
]
if '*' not in ALLOWED_HOSTS and not DEBUG:
    ALLOWED_HOSTS.extend(['.onrender.com', '.vercel.app', '.pythonanywhere.com'])

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get(
        'CSRF_TRUSTED_ORIGINS',
        'https://*.onrender.com,https://*.vercel.app,https://*.pythonanywhere.com,http://localhost:8000,http://127.0.0.1:8000'
    ).split(',') if o.strip()
]

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

# WhiteNoise Static Files Serving
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Security Headers & Cookies
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True') == 'True'
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

if SECURE_SSL_REDIRECT:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
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

