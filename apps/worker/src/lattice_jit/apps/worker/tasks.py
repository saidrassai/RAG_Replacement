from __future__ import annotations

import json
import logging
import traceback
from uuid import UUID

from lattice_jit.core import build_container, get_settings

from .celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

TASK_RETRY_CONFIG = {
    "autoretry_for": (Exception,),
    "max_retries": settings.celery_task_max_retries,
    "retry_backoff": True,
    "retry_jitter": True,
    "acks_late": True,
    "reject_on_worker_lost": True,
}


def _push_to_dlq(task_name: str, args: tuple, kwargs: dict, exc: Exception, tb: str) -> None:
    if not settings.celery_dlq_enabled:
        return
    import redis

    try:
        r = redis.from_url(settings.redis_url)
        payload = json.dumps({
            "task": task_name,
            "args": [str(a) for a in args],
            "kwargs": {k: str(v) for k, v in kwargs.items()},
            "error": str(exc),
            "traceback": tb,
        })
        r.rpush("lattice_jit:dlq", payload)
    except Exception:
        logger.warning("Failed to push to DLQ", exc_info=True)


@celery_app.task(
    name="lattice_jit.snapshot.continue_ingest",
    **TASK_RETRY_CONFIG,
)
def continue_snapshot_ingest(snapshot_id: str) -> dict[str, str]:
    container = build_container(force_inline_phase_b=True)
    response = container.snapshot_service.continue_ingest(UUID(snapshot_id))
    snapshot = container.repository.get_source_snapshot(response.snapshot_id)
    if snapshot is not None:
        container.governance_service.record_snapshot_ingested(
            tenant_id=snapshot.tenant_id,
            snapshot_id=response.snapshot_id,
            repo_path=snapshot.repo_path,
            node_count=len(container.repository.list_snapshot_nodes(response.snapshot_id)),
        )
    return {
        "status": response.status.value,
        "snapshot_id": str(response.snapshot_id),
    }


@celery_app.task(
    name="lattice_jit.phase_b.verify",
    **TASK_RETRY_CONFIG,
)
def phase_b_verify(answer_id: str) -> None:
    container = build_container(force_inline_phase_b=True)
    container.phase_b_service.verify(UUID(answer_id))


@celery_app.task(
    name="lattice_jit.cache.invalidate",
    **TASK_RETRY_CONFIG,
)
def invalidate_manifest(manifest_id: str) -> dict[str, str]:
    container = build_container(force_inline_phase_b=True)
    manifest = container.repository.invalidate_manifest(UUID(manifest_id))
    if manifest is None:
        return {"status": "missing", "manifest_id": manifest_id}
    container.cache_store.delete(f"manifest:{manifest.query_hash}")
    container.audit_service.record(
        tenant_id=manifest.tenant_id,
        event_type="manifest_invalidated",
        resource_type="compiled_context_manifest",
        resource_id=manifest.manifest_id,
        payload={"query_hash": manifest.query_hash},
    )
    return {"status": "invalidated", "manifest_id": manifest_id}


@celery_app.task(
    name="lattice_jit.governance.scan",
    **TASK_RETRY_CONFIG,
)
def governance_scan(tenant_id: str | None = None) -> dict[str, int]:
    container = build_container(force_inline_phase_b=True)
    resolved_tenant_id = UUID(tenant_id) if tenant_id is not None else container.settings.default_tenant_id
    return container.governance_service.run_governance_scan(resolved_tenant_id)


# Register task failure handler via Celery signal
@celery_app.task(name="lattice_jit.internal.dlq_handler", bind=True, max_retries=0)
def _dlq_handler_task(self, task_name: str, args: list, kwargs: dict, error: str, traceback_str: str) -> None:  # noqa: ARG001
    if not settings.celery_dlq_enabled:
        return
    import redis

    try:
        r = redis.from_url(settings.redis_url)
        payload = json.dumps({
            "task": task_name,
            "args": args,
            "kwargs": kwargs,
            "error": error,
            "traceback": traceback_str,
        })
        r.rpush("lattice_jit:dlq", payload)
    except Exception:
        logger.warning("Failed to push to DLQ", exc_info=True)
