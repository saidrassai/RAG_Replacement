from __future__ import annotations

from uuid import UUID

from lattice_jit.contracts import PhaseBMode
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
