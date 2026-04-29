from __future__ import annotations

from celery import Celery
from lattice_jit.core import get_settings

settings = get_settings()
celery_app = Celery(
    "lattice_jit",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.task_always_eager = settings.celery_eager
celery_app.conf.task_default_queue = "lattice_jit"
celery_app.conf.task_soft_time_limit = settings.celery_task_soft_time_limit
celery_app.conf.task_time_limit = settings.celery_task_soft_time_limit + 300
celery_app.conf.worker_send_task_events = True
celery_app.conf.task_send_sent_event = True
