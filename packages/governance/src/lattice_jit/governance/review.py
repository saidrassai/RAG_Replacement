from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from lattice_jit.contracts import AnswerEnvelope, ConfidenceBand, PolicyBundle, ReviewItem, ReviewRiskLevel
from lattice_jit.core import stable_hash
from lattice_jit.storage import StorageRepository

from .audit import AuditService
from .calibration import CalibrationService
from .load_shedding import LoadSheddingService


@dataclass(slots=True)
class GovernanceService:
    repository: StorageRepository
    audit_service: AuditService
    calibration_service: CalibrationService
    load_shedding_service: LoadSheddingService

    def maybe_queue_review(self, answer: AnswerEnvelope, policy_bundle: PolicyBundle) -> None:
        self.audit_service.record(
            tenant_id=answer.tenant_id,
            event_type="answer_recorded",
            resource_type="answer",
            resource_id=answer.answer_id,
            payload={
                "phase": answer.phase.value,
                "confidence_band": answer.confidence_band.value,
                "provisional": answer.provisional,
            },
        )
        if not policy_bundle.human_gate_required and answer.confidence_band != ConfidenceBand.LOW:
            return
        item = ReviewItem(
            tenant_id=answer.tenant_id,
            fact_fingerprint=stable_hash(
                policy_bundle.query_class,
                answer.confidence_band.value,
                *(provenance.node_id for provenance in answer.provenance[:5]),
                *answer.conflict_flags,
            ),
            fact_type=policy_bundle.query_class,
            canonical_node_id=answer.provenance[0].node_id if answer.provenance else None,
            dedup_count=1,
            risk_level=ReviewRiskLevel.HIGH if policy_bundle.human_gate_required else ReviewRiskLevel.MEDIUM,
            sample_rate=0.05,
            evidence_count=len(answer.provenance),
        )
        queued = self.load_shedding_service.queue(item)
        self.audit_service.record(
            tenant_id=answer.tenant_id,
            event_type="review_queued",
            resource_type="review_item",
            resource_id=queued.review_item_id,
            payload={
                "fact_type": queued.fact_type,
                "dedup_count": queued.dedup_count,
                "risk_level": queued.risk_level.value,
            },
        )

    def list_review_queue(self, tenant_id: UUID) -> list[ReviewItem]:
        return self.repository.list_review_items(tenant_id)

    def record_snapshot_ingested(
        self,
        *,
        tenant_id: UUID,
        snapshot_id: UUID,
        repo_path: str,
        node_count: int,
    ) -> None:
        self.audit_service.record(
            tenant_id=tenant_id,
            event_type="snapshot_ingested",
            resource_type="snapshot",
            resource_id=snapshot_id,
            payload={
                "repo_path": repo_path,
                "node_count": node_count,
            },
        )

    def record_policy_evaluation(
        self,
        *,
        tenant_id: UUID,
        policy_bundle: PolicyBundle,
    ) -> None:
        self.audit_service.record(
            tenant_id=tenant_id,
            event_type="policy_evaluated",
            resource_type="policy_bundle",
            resource_id=policy_bundle.policy_bundle_id,
            payload={
                "query_class": policy_bundle.query_class,
                "phase_b_required": policy_bundle.phase_b_required,
                "human_gate_required": policy_bundle.human_gate_required,
            },
        )

    def run_governance_scan(self, tenant_id: UUID) -> dict[str, int]:
        pending = self.repository.list_review_items(tenant_id)
        self.audit_service.record(
            tenant_id=tenant_id,
            event_type="governance_scan",
            resource_type="tenant",
            payload={
                "pending_review_items": len(pending),
            },
        )
        return {"pending_review_items": len(pending)}
