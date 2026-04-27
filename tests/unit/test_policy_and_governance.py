from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from lattice_jit.contracts import KnowledgeNode, NodeType, PhaseBMode, ReviewItem, ReviewRiskLevel
from lattice_jit.core import utcnow
from lattice_jit.governance import apply_adaptive_decay
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
