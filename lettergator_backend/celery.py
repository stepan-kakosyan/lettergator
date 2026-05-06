import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lettergator_backend.settings")

app = Celery("lettergator_backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
