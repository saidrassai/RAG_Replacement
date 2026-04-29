from __future__ import annotations

from uuid import uuid4

from lattice_jit.apps.worker.tasks import continue_snapshot_ingest, governance_scan, invalidate_manifest
from lattice_jit.contracts import PhaseBMode, QueryRequest, SnapshotGitRequest


def _configure_worker_env(monkeypatch, test_settings) -> None:
    monkeypatch.setenv("LJIT_DATABASE_URL", test_settings.database_url)
    monkeypatch.setenv("LJIT_REDIS_URL", test_settings.redis_url)
    monkeypatch.setenv("LJIT_CELERY_EAGER", "true")


def test_worker_can_continue_pending_snapshot(container, sample_workspace, monkeypatch, test_settings) -> None:
    _configure_worker_env(monkeypatch, test_settings)
    tenant_id = uuid4()
    request = SnapshotGitRequest(
        tenant_id=tenant_id,
        repo_path=str(sample_workspace),
        include_globs=["*.py", "*.md"],
    )
    snapshot_id = container.snapshot_service.create_pending_snapshot(request)

    result = continue_snapshot_ingest(str(snapshot_id))
    nodes = container.repository.list_snapshot_nodes(snapshot_id)

    assert result["status"] == "completed"
    assert len(nodes) >= 2


def test_governance_audit_and_load_shedding(container, sample_workspace) -> None:
    tenant_id = uuid4()
    snapshot = container.snapshot_service.ingest(
        SnapshotGitRequest(
            tenant_id=tenant_id,
            repo_path=str(sample_workspace),
            include_globs=["*.py", "*.md"],
        )
    )

    first = container.query_service.run(
        QueryRequest(
            tenant_id=tenant_id,
            query="What does our compliance policy say about customer identifiers?",
            snapshot_id=snapshot.snapshot_id,
            phase_b_mode=PhaseBMode.AUTO,
        )
    )
    second = container.query_service.run(
        QueryRequest(
            tenant_id=tenant_id,
            query="What does our compliance policy say about customer identifiers?",
            snapshot_id=snapshot.snapshot_id,
            phase_b_mode=PhaseBMode.AUTO,
        )
    )
    reviews = container.governance_service.list_review_queue(tenant_id)
    audit_events = container.audit_service.list_events(tenant_id)
    feedback = container.calibration_service.record_feedback(
        tenant_id=tenant_id,
        target_type="answer",
        target_id=first.answer_id,
        label_type="correct",
        label_value=1.0,
    )
    feedback_labels = container.calibration_service.list_feedback(tenant_id)

    assert first.phase_b_status == "complete"
    assert second.phase_b_status == "complete"
    assert len(reviews) == 1
    assert reviews[0].dedup_count == 2
    assert feedback.label_type == "correct"
    assert len(feedback_labels) == 1
    assert any(event.event_type == "policy_evaluated" for event in audit_events)
    assert any(event.event_type == "answer_recorded" for event in audit_events)
    assert any(event.event_type == "review_queued" for event in audit_events)


def test_manifest_invalidation_and_governance_scan(
    container,
    sample_workspace,
    monkeypatch,
    test_settings,
) -> None:
    _configure_worker_env(monkeypatch, test_settings)
    tenant_id = uuid4()
    snapshot = container.snapshot_service.ingest(
        SnapshotGitRequest(
            tenant_id=tenant_id,
            repo_path=str(sample_workspace),
            include_globs=["*.py", "*.md"],
        )
    )
    response = container.query_service.run(
        QueryRequest(
            tenant_id=tenant_id,
            query="Which file mentions auth?",
            snapshot_id=snapshot.snapshot_id,
            phase_b_mode=PhaseBMode.OFF,
        )
    )

    invalidation = invalidate_manifest(str(response.manifest_id))
    scan = governance_scan(str(tenant_id))
    manifest = container.repository.get_manifest(response.manifest_id)

    assert invalidation["status"] == "invalidated"
    assert manifest is not None
    assert manifest.status.value == "invalidated"
    assert "pending_review_items" in scan
    assert "high_risk_pending" in scan
    assert "feedback_labels" in scan
    assert "nodes_scanned" in scan
    assert "decayed_nodes" in scan


# ── Worker Health + DLQ Tests ──────────────────────────────────────────────


def test_worker_health_endpoint_returns_status(test_settings) -> None:
    from lattice_jit.apps.api.main import create_app

    app = create_app(settings=test_settings)
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/v1/worker/health")
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert "broker" in payload


def test_worker_dlq_endpoint_requires_tenant_id(test_settings) -> None:
    from lattice_jit.apps.api.main import create_app, get_container
    from lattice_jit.core import build_container

    test_container = build_container(test_settings)
    app = create_app(settings=test_settings)
    app.dependency_overrides[get_container] = lambda: test_container
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/v1/worker/dlq", params={"tenant_id": str(uuid4())})
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "total" in payload


def test_worker_tasks_have_retry_config() -> None:
    from lattice_jit.apps.worker.tasks import (
        continue_snapshot_ingest,
        governance_scan,
        invalidate_manifest,
        phase_b_verify,
    )

    for task in (continue_snapshot_ingest, phase_b_verify, invalidate_manifest, governance_scan):
        assert task.max_retries == 3
        assert task.autoretry_for is not None
        assert task.acks_late is True
