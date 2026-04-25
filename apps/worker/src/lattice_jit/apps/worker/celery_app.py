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
