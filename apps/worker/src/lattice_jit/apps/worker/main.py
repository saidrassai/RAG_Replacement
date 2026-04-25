from __future__ import annotations

from .celery_app import celery_app


def main() -> None:
    from . import tasks  # noqa: F401

    del tasks
    celery_app.worker_main(["worker", "--loglevel=INFO", "--pool=solo"])
