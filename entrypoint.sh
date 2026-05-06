#!/bin/sh
set -e

echo "Applying migrations..."
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn lettergator_backend.wsgi:application --bind 0.0.0.0:8040
