# core/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")

# Load config from Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# limit concurrency to 1 worker
app.conf.update(worker_concurrency=1)

# Set Celery configuration option
app.conf.broker_connection_retry_on_startup = True

app.autodiscover_tasks()
