import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'default-insecure-django-secret-key-change-in-production')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get(
        'DJANGO_ALLOWED_HOSTS',
        '*'
    ).split(',') if h.strip()
]
if '*' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.extend(['.onrender.com', '.vercel.app', '.pythonanywhere.com', 'ai-timemanagemant.vercel.app', 'ai-timemanagemant.onrender.com', 'localhost', '127.0.0.1'])

# Reverse Proxy SSL & Host Support (Critical for Vercel, Render, Heroku)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# CSRF Trusted Origins for Cloud & Local
CSRF_TRUSTED_ORIGINS = [
    'https://*.vercel.app',
    'https://*.onrender.com',
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
    CSRF_TRUSTED_ORIGINS.extend([c.strip() for c in custom_csrf.split(',') if c.strip()])

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',

    # Core Application Apps
    'apps.accounts',
    'apps.projects',
    'apps.tasks',
    'apps.tracking',
    'apps.scheduling',
    'apps.notifications',
    'apps.analytics',
    'apps.ai',
    'apps.audit',
]

MIDDLEWARE = [ 
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.audit.middleware.AuditMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.tracking.context_processors.active_timer_context',
                'apps.notifications.context_processors.unread_notifications_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database Configuration (Auto-detect DATABASE_URL from Neon/Cloud, fallback to MySQL or SQLite)
is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
database_url = os.environ.get('DATABASE_URL')
if database_url:
    conn_max_age = 0 if is_serverless else int(os.environ.get('DB_CONN_MAX_AGE', '600'))
    try:
        import dj_database_url
        DATABASES = {
            'default': dj_database_url.parse(database_url, conn_max_age=conn_max_age, ssl_require=True)
        }
    except Exception:
        from urllib.parse import urlparse
        parsed_db = urlparse(database_url)
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql' if 'postgres' in parsed_db.scheme else 'django.db.backends.mysql',
                'NAME': parsed_db.path.lstrip('/'),
                'USER': parsed_db.username or '',
                'PASSWORD': parsed_db.password or '',
                'HOST': parsed_db.hostname or 'localhost',
                'PORT': str(parsed_db.port or 5432),
                'CONN_MAX_AGE': conn_max_age,
            }
        }
    db_engine = DATABASES['default'].get('ENGINE', '')
    if 'postgresql' in db_engine:
        DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True
    DATABASES['default']['CONN_HEALTH_CHECKS'] = True
else:
    DB_ENGINE = os.environ.get('DB_ENGINE', 'mysql').lower()
    if DB_ENGINE == 'sqlite3' or os.environ.get('RENDER') or is_serverless:
        sqlite_path = '/tmp/db.sqlite3' if is_serverless else (BASE_DIR / 'db.sqlite3')
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': sqlite_path,
                'CONN_MAX_AGE': 0 if is_serverless else 600,
            }
        }
    else:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': os.environ.get('DB_NAME', 'ai_time_mng'),
                'USER': os.environ.get('DB_USER', 'root'),
                'PASSWORD': os.environ.get('DB_PASSWORD', 'dinesh@19052008'),
                'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
                'PORT': os.environ.get('DB_PORT', '3306'),
                'CONN_MAX_AGE': 600,
                'OPTIONS': {
                    'charset': 'utf8mb4',
                    'init_command': "SET sql_mode='STRICT_TRANS_TABLES', innodb_strict_mode=1;",
                },
            }
        }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization & Timezones
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static and Media files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
WHITENOISE_USE_FINDERS = True

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'user_dashboard'
LOGOUT_REDIRECT_URL = 'login'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Cache Configuration (Redis with LocMem fallback if redis server unreachable)
REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')

def _is_redis_reachable(url):
    if os.environ.get('USE_LOCMEM_CACHE') == 'True' or 'test' in sys.argv:
        return False
    try:
        from urllib.parse import urlparse
        import socket
        parsed = urlparse(url)
        host = parsed.hostname or '127.0.0.1'
        port = parsed.port or 6379
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.04)
        res = s.connect_ex((host, port))
        s.close()
        return res == 0
    except Exception:
        return False

redis_alive = _is_redis_reachable(REDIS_URL)
use_locmem = os.environ.get('USE_LOCMEM_CACHE') == 'True' or not redis_alive or 'test' in sys.argv

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache' if use_locmem else 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'unique-snowflake' if use_locmem else REDIS_URL,
    }
}

# Celery Configuration
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER') == 'True' or not redis_alive or 'test' in sys.argv

# Fast password hasher for tests
if 'test' in sys.argv:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Brevo Transactional Email Configuration
SITE_URL = os.environ.get('SITE_URL') or os.environ.get('APP_URL') or ('https://ai-timemanagemant.vercel.app' if (os.environ.get('VERCEL') or not DEBUG) else 'http://127.0.0.1:8000')
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
BREVO_SENDER_EMAIL = os.environ.get('BREVO_SENDER_EMAIL', 'noreply@aitimemanagement.com')
BREVO_SENDER_NAME = os.environ.get('BREVO_SENDER_NAME', 'AI Time Management')
BREVO_DEFAULT_TEMPLATE_ID = os.environ.get('BREVO_DEFAULT_TEMPLATE_ID', '')
BREVO_WEBHOOK_TOKEN = os.environ.get('BREVO_WEBHOOK_TOKEN', 'brevo_webhook_secret_token_secure_xyz123')
BREVO_API_URL = 'https://api.brevo.com/v3/smtp/email'

# AI Provider Configuration
AI_PROVIDER = os.environ.get('AI_PROVIDER', 'mock')
AI_API_KEY = os.environ.get('AI_API_KEY', '')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.6-flash')

# Structured Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'structured': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'structured',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}
