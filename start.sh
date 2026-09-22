#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -e

# If running Celery inside the same instance (ideal for Render Free tier):
if [ "${RUN_CELERY_IN_WEB}" = "True" ]; then
    echo "==> Starting Celery Worker & Beat scheduler in background..."
    celery -A config worker -B --loglevel=info --concurrency=2 &
fi

echo "==> Starting Gunicorn WSGI server on port ${PORT:-8000}..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120
