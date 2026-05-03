"""
Celery application factory for TABLESYS async task processing.

Broker and result backend both use Redis.
Tasks are auto-discovered from app.tasks package.
"""
from celery import Celery
from .config import settings

celery_app = Celery(
    "tablesys",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.generation", "app.tasks.registration_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_track_started=True,          # Reports STARTED state so frontend sees it immediately
    result_expires=3600,              # Keep results for 1 hour
    worker_prefetch_multiplier=1,     # Fair dispatch — one task per worker at a time
    task_acks_late=True,              # Only ack after task completes (safe retry on crash)
)
