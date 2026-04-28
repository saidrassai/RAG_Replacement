from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from lattice_jit.contracts import KnowledgeNode, NodeType, PhaseBMode, ReviewItem, ReviewRiskLevel
from lattice_jit.core import utcnow
from lattice_jit.governance import (
    LoadSheddingService,
    apply_adaptive_decay,
    apply_calibration,
    build_calibration_curve,
    compute_pava,
)
from lattice_jit.policy import PolicyEvaluator


def test_policy_bundle_marks_compliance_queries_for_phase_b() -> None:
    evaluator = PolicyEvaluator()

    bundle = evaluator.evaluate(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        query="What does our PCI policy require?",
        phase_b_mode=PhaseBMode.AUTO,
    )

    assert bundle.query_class == "compliance"
    assert bundle.phase_b_required is True
    assert bundle.human_gate_required is True


def test_adaptive_decay_drops_for_old_volatile_unused_nodes() -> None:
    decayed = apply_adaptive_decay(
        source_confidence=0.9,
        age_days=90,
        volatility_score=0.8,
        unused_weeks=8,
    )

    assert decayed < 0.4


def test_governance_scan_applies_decay_and_reports_metrics(container) -> None:
    tenant_id = uuid4()
    stale_timestamp = utcnow() - timedelta(days=120)
    node = KnowledgeNode(
        tenant_id=tenant_id,
        snapshot_id=None,
        node_type=NodeType.SECTION,
        title="stale-policy.md",
        body_text="old governance evidence",
        content_hash="stale-hash",
        source_confidence=0.9,
        serving_confidence=0.9,
        volatility_score=0.7,
        created_at=stale_timestamp,
        updated_at=stale_timestamp,
    )
    container.repository.upsert_nodes([node])
    container.repository.upsert_review_item(
        ReviewItem(
            tenant_id=tenant_id,
            fact_fingerprint="fact-1",
            fact_type="decision",
            risk_level=ReviewRiskLevel.HIGH,
            dedup_count=1,
            evidence_count=1,
        )
    )
    container.calibration_service.record_feedback(
        tenant_id=tenant_id,
        target_type="answer",
        target_id=uuid4(),
        label_type="correct",
        label_value=1.0,
    )

    result = container.governance_service.run_governance_scan(tenant_id)
    refreshed_node = container.repository.get_node(node.node_id)

    assert result["pending_review_items"] == 1
    assert result["high_risk_pending"] == 1
    assert result["feedback_labels"] == 1
    assert result["nodes_scanned"] == 1
    assert result["decayed_nodes"] == 1
    assert refreshed_node is not None
    assert refreshed_node.serving_confidence < 0.9


# ── Isotonic Calibration Tests ─────────────────────────────────────────────


def test_pava_preserves_monotonic_sequence() -> None:
    result = compute_pava([0.1, 0.3, 0.5, 0.7, 0.9])
    assert result == [0.1, 0.3, 0.5, 0.7, 0.9]


def test_pava_corrects_non_monotonic_sequence() -> None:
    result = compute_pava([0.5, 0.3, 0.7, 0.2, 0.9])
    for i in range(len(result) - 1):
        assert result[i] <= result[i + 1]


def test_pava_known_output() -> None:
    result = compute_pava([0.2, 0.1, 0.4, 0.3], [1.0, 1.0, 1.0, 1.0])
    assert result[0] == result[1]
    assert result[2] == result[3]
    assert result[0] <= result[2]


def test_pava_empty_input() -> None:
    assert compute_pava([]) == []


def test_pava_rejects_mismatched_weights() -> None:
    import pytest as pt
    with pt.raises(ValueError, match="same length"):
        compute_pava([0.5, 0.6], [1.0])


def test_build_calibration_curve_empty() -> None:
    assert build_calibration_curve([], []) == []


def test_build_calibration_curve_single_pair() -> None:
    result = build_calibration_curve([0.8], [0.9])
    assert len(result) == 1
    assert result[0] == (0.8, 0.9)


def test_build_calibration_curve_non_monotonic() -> None:
    predicted = [0.5, 0.6, 0.7, 0.6, 0.9, 0.75]
    actual = [0.4, 0.5, 0.55, 0.55, 0.8, 0.8]
    result = build_calibration_curve(predicted, actual)
    for i in range(len(result) - 1):
        assert result[i][1] <= result[i + 1][1]
    assert all(0.0 <= v <= 1.0 for _, v in result)


def test_apply_calibration_exact_match() -> None:
    curve = [(0.0, 0.1), (0.5, 0.5), (1.0, 0.9)]
    assert apply_calibration(0.5, curve) == 0.5


def test_apply_calibration_interpolation() -> None:
    curve = [(0.0, 0.0), (1.0, 1.0)]
    result = apply_calibration(0.5, curve)
    assert 0.45 < result < 0.55


def test_apply_calibration_below_curve() -> None:
    curve = [(0.2, 0.3), (1.0, 0.9)]
    assert apply_calibration(0.1, curve) == 0.3


def test_apply_calibration_above_curve() -> None:
    curve = [(0.0, 0.1), (0.8, 0.7)]
    assert apply_calibration(0.9, curve) == 0.7


def test_apply_calibration_empty_curve() -> None:
    assert apply_calibration(0.5, []) == 0.5


def test_governance_scan_with_calibration_metrics(container) -> None:
    tenant_id = uuid4()
    node = KnowledgeNode(
        tenant_id=tenant_id,
        snapshot_id=None,
        node_type=NodeType.SECTION,
        title="calibrated-node.md",
        body_text="evidence",
        content_hash="cal-hash",
        source_confidence=0.9,
        serving_confidence=0.9,
        volatility_score=0.0,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    container.repository.upsert_nodes([node])
    container.calibration_service.record_feedback(
        tenant_id=tenant_id,
        target_type="node",
        target_id=node.node_id,
        label_type="correct",
        label_value=0.6,
    )
    container.calibration_service.record_feedback(
        tenant_id=tenant_id,
        target_type="node",
        target_id=node.node_id,
        label_type="correct",
        label_value=0.5,
    )
    container.calibration_service.record_feedback(
        tenant_id=tenant_id,
        target_type="node",
        target_id=node.node_id,
        label_type="correct",
        label_value=0.4,
    )

    result = container.governance_service.run_governance_scan(tenant_id)
    assert "calibrated_nodes" in result
    assert "calibration_curve_segments" in result
    assert isinstance(result["calibrated_nodes"], int)
    assert isinstance(result["calibration_curve_segments"], int)


# ── Load Shedding Tests ────────────────────────────────────────────────────


def test_load_shedding_disabled_queues_everything() -> None:
    from lattice_jit.storage import StorageRepository, build_database

    db = build_database("sqlite+pysqlite:///:memory:")
    repo = StorageRepository(db)
    repo.create_schema()
    service = LoadSheddingService(repo, enabled=False)
    item = ReviewItem(
        tenant_id=uuid4(),
        fact_fingerprint="fingerprint-1",
        fact_type="compliance",
        risk_level=ReviewRiskLevel.LOW,
        sample_rate=0.01,
    )
    result = service.queue(item)
    assert result.review_item_id == item.review_item_id


def test_load_shedding_high_risk_always_queued() -> None:
    from lattice_jit.storage import StorageRepository, build_database

    db = build_database("sqlite+pysqlite:///:memory:")
    repo = StorageRepository(db)
    repo.create_schema()
    service = LoadSheddingService(repo, enabled=True, max_items_per_minute=1)
    item = ReviewItem(
        tenant_id=uuid4(),
        fact_fingerprint="fingerprint-high",
        fact_type="compliance",
        risk_level=ReviewRiskLevel.HIGH,
        sample_rate=0.001,
    )
    result = service.queue(item)
    assert result.review_item_id == item.review_item_id


def test_load_shedding_dedup_still_works() -> None:
    from lattice_jit.storage import StorageRepository, build_database

    db = build_database("sqlite+pysqlite:///:memory:")
    repo = StorageRepository(db)
    repo.create_schema()
    service = LoadSheddingService(repo, enabled=False)
    tenant_id = uuid4()
    fp = "fingerprint-dedup"
    item1 = ReviewItem(
        tenant_id=tenant_id,
        fact_fingerprint=fp,
        fact_type="general",
        risk_level=ReviewRiskLevel.MEDIUM,
        sample_rate=0.1,
        dedup_count=1,
    )
    service.queue(item1)
    item2 = ReviewItem(
        tenant_id=tenant_id,
        fact_fingerprint=fp,
        fact_type="general",
        risk_level=ReviewRiskLevel.MEDIUM,
        sample_rate=0.1,
        dedup_count=1,
    )
    result = service.queue(item2)
    assert result.dedup_count == 2


def test_load_shedding_sampling_deterministic_behavior() -> None:
    from lattice_jit.storage import StorageRepository, build_database

    db = build_database("sqlite+pysqlite:///:memory:")
    repo = StorageRepository(db)
    repo.create_schema()
    service = LoadSheddingService(repo, enabled=True, max_items_per_minute=1000)
    tenant_id = uuid4()
    queued = 0
    for i in range(100):
        item = ReviewItem(
            tenant_id=tenant_id,
            fact_fingerprint=f"fp-sampling-{i}",
            fact_type="general",
            risk_level=ReviewRiskLevel.LOW,
            sample_rate=0.5,
        )
        service.queue(item)
        stored = repo.get_review_item_by_fingerprint(tenant_id, f"fp-sampling-{i}")
        if stored is not None:
            queued += 1
    assert 20 <= queued <= 80
