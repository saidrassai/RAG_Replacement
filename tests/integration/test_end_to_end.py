from __future__ import annotations

from uuid import uuid4

from lattice_jit.contracts import PhaseBMode, QueryRequest, SnapshotGitRequest


def test_full_vertical_slice(container, sample_workspace) -> None:
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
            query="Where is auth enforced and what does policy say?",
            snapshot_id=snapshot.snapshot_id,
            phase_b_mode=PhaseBMode.FORCE,
        )
    )
    latest = container.query_service.get_answer(response.answer_id, tenant_id=tenant_id)

    assert response.phase_a.provisional is True
    assert response.phase_a.provenance
    assert response.phase_b_status == "complete"
    assert latest.phase.value == "B"
    assert "Phase B verification" in latest.answer_text


def test_context_manifest_is_reused_from_cache(container, sample_workspace) -> None:
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
            query="Which file mentions auth?",
            snapshot_id=snapshot.snapshot_id,
            phase_b_mode=PhaseBMode.OFF,
        )
    )
    second = container.query_service.run(
        QueryRequest(
            tenant_id=tenant_id,
            query="Which file mentions auth?",
            snapshot_id=snapshot.snapshot_id,
            phase_b_mode=PhaseBMode.OFF,
        )
    )

    assert first.manifest_id == second.manifest_id
