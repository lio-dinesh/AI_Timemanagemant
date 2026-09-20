import socket
from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Check if Redis is running locally on port 6379
def _is_redis_available(host='127.0.0.1', port=6379):
    try:
        s = socket.socket()
        s.settimeout(0.5)
        res = s.connect_ex((host, port))
        s.close()
        return res == 0
    except Exception:
        return False

if not _is_redis_available():
    # Graceful fallback for local development without standalone Redis server running
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'ai_time_mng_locmem',
        }
    }
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
