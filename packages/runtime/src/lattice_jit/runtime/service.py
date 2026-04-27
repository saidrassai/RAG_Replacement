from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from lattice_jit.contracts import (
    AnswerEnvelope,
    AnswerPhase,
    AnswerStatus,
    PhaseBMode,
    QueryRequest,
    QueryResponse,
)
from lattice_jit.core import NotFoundError, generate_id, utcnow
from lattice_jit.governance import GovernanceService
from lattice_jit.lattice import build_provenance, compute_confidence_band
from lattice_jit.model_proxy import ModelProvider
from lattice_jit.policy import PolicyEvaluatorProtocol
from lattice_jit.storage import StorageRepository

from .compiler import ContextCompiler
from .phase_b import PhaseBScheduler
from .routing import SemanticRouter


@dataclass(slots=True)
class QueryService:
    repository: StorageRepository
    router: SemanticRouter
    compiler: ContextCompiler
    policy_evaluator: PolicyEvaluatorProtocol
    model_provider: ModelProvider
    governance_service: GovernanceService
    phase_b_scheduler: PhaseBScheduler

    def run(self, request: QueryRequest) -> QueryResponse:
        snapshot = (
            self.repository.get_source_snapshot(request.snapshot_id)
            if request.snapshot_id is not None
            else self.repository.get_latest_snapshot(request.tenant_id)
        )
        if snapshot is None:
            raise NotFoundError("No source snapshot found for the requested tenant.")

        snapshot_nodes = self.repository.list_snapshot_nodes(snapshot.snapshot_id)
        selected_nodes = self.router.select(request.query, snapshot_nodes, request.subgraph_ids)
        policy_bundle = self.policy_evaluator.evaluate(request.tenant_id, request.query, request.phase_b_mode)
        self.repository.store_policy_bundle(policy_bundle)
        self.governance_service.record_policy_evaluation(
            tenant_id=request.tenant_id,
            policy_bundle=policy_bundle,
        )

        manifest = self.compiler.compile(
            tenant_id=request.tenant_id,
            query=request.query,
            selected_nodes=selected_nodes,
            policy_bundle=policy_bundle,
        )
        evidence_nodes = self.repository.get_nodes_by_ids(item.node_id for item in manifest.items)
        provenance = build_provenance(manifest, evidence_nodes)
        answer_id = generate_id()
        phase_b_status = "off"
        answer = AnswerEnvelope(
            answer_id=answer_id,
            tenant_id=request.tenant_id,
            phase=AnswerPhase.A,
            status=AnswerStatus.COMPLETE,
            answer_text=self.model_provider.generate(request.query, manifest, evidence_nodes, policy_bundle),
            confidence_band=compute_confidence_band(evidence_nodes),
            provisional=True,
            provenance=provenance,
            conflict_flags=[],
            manifest_id=manifest.manifest_id,
            phase_b_status=phase_b_status,
            created_at=utcnow(),
        )
        self.repository.store_answer_event(answer)

        if request.phase_b_mode != PhaseBMode.OFF and policy_bundle.phase_b_required:
            phase_b_status = self.phase_b_scheduler.schedule(answer.answer_id)
            self.repository.update_phase_a_phase_b_status(answer.answer_id, phase_b_status)
            answer.phase_b_status = phase_b_status
        elif request.phase_b_mode == PhaseBMode.FORCE:
            phase_b_status = self.phase_b_scheduler.schedule(answer.answer_id)
            self.repository.update_phase_a_phase_b_status(answer.answer_id, phase_b_status)
            answer.phase_b_status = phase_b_status

        self.governance_service.maybe_queue_review(answer, policy_bundle)
        return QueryResponse(
            answer_id=answer.answer_id,
            phase_a=answer,
            phase_b_status=phase_b_status,
            manifest_id=manifest.manifest_id,
        )

    def get_answer(self, answer_id: UUID) -> AnswerEnvelope:
        answer = self.repository.get_latest_answer(answer_id)
        if answer is None:
            raise NotFoundError(f"Answer {answer_id} was not found.")
        return answer
