from __future__ import annotations

from uuid import UUID

from lattice_jit.contracts import PhaseBMode, PolicyBundle
from lattice_jit.core import stable_hash


class PolicyEvaluator:
    def evaluate(self, tenant_id: UUID, query: str, phase_b_mode: PhaseBMode) -> PolicyBundle:
        lowered = query.lower()
        query_class = self._classify(lowered)
        phase_b_required = phase_b_mode.value == "force" or (
            phase_b_mode.value == "auto" and query_class in {"compliance", "security", "governance"}
        )
        human_gate_required = query_class in {"compliance", "security"}
        redaction_rules = ["mask_identifiers"] if human_gate_required else []
        return PolicyBundle(
            tenant_id=tenant_id,
            query_class=query_class,
            tool_allowlist=["git_local"],
            redaction_rules=redaction_rules,
            max_tokens=12_000 if human_gate_required else 16_000,
            phase_b_required=phase_b_required,
            human_gate_required=human_gate_required,
            opa_decision_hash=stable_hash(tenant_id, query_class, phase_b_mode),
        )

    def _classify(self, lowered_query: str) -> str:
        if any(term in lowered_query for term in ("hipaa", "pci", "gdpr", "ccpa", "policy", "compliance")):
            return "compliance"
        if any(term in lowered_query for term in ("security", "incident", "breach")):
            return "security"
        if any(term in lowered_query for term in ("cost", "budget", "price")):
            return "cost"
        return "general"
