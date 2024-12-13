# core/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")

# Load config from Django settings; the prefix CELERY_ is optional
app.config_from_object("django.conf:settings", namespace="CELERY")

# Discover tasks from all installed apps
app.autodiscover_tasks()
