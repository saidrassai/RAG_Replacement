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

        # Financial Schema: inject computation guidance into the query for the LLM
        # (applied AFTER retrieval so it doesn't affect router node selection)
        from .financial_schema import ground_query
        llm_query = ground_query(request.query)

        answer_id = generate_id()
        phase_b_status = "off"
        answer = AnswerEnvelope(
            answer_id=answer_id,
            tenant_id=request.tenant_id,
            phase=AnswerPhase.A,
            status=AnswerStatus.COMPLETE,
            answer_text=self.model_provider.generate(llm_query, manifest, evidence_nodes, policy_bundle),
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

    def get_answer(self, answer_id: UUID, *, tenant_id: UUID) -> AnswerEnvelope:
        answer = self.repository.get_latest_answer(answer_id)
        if answer is None:
            raise NotFoundError(f"Answer {answer_id} was not found.")
        if answer.tenant_id != tenant_id:
            raise NotFoundError(f"Answer {answer_id} was not found.")
        return answer


# ── Fix 3: LLM Section Re-Ranking ──────────────────────────────────────────


def _llm_rerank_sections(model_provider, query: str, nodes: list) -> list | None:
    """Use LLM to select relevant sections from top candidates.

    Sends section summaries to the model and asks which sections
    are relevant to the query. Returns filtered node list or None
    if re-ranking fails (caller falls back to original nodes).
    """
    try:
        sections: list[tuple[int, str, str]] = []
        for idx, node in enumerate(nodes[:50]):
            title = node.title or ""
            snippet = (node.body_text or "")[:300]
            sections.append((idx, title, snippet))

        if len(sections) < 3:
            return None

        section_list = "\n".join(
            f"[{i + 1}] {title}\n   {snippet[:150]}"
            for i, (_, title, snippet) in enumerate(sections[:30])
        )

        prompt = (
            f"Query: {query}\n\n"
            f"Below are {min(30, len(sections))} candidate document sections. "
            "Select the sections (by number) that contain information "
            "relevant to answering the query. Return ONLY numbers separated "
            "by commas, e.g.: 2,5,7,12\n\n"
            f"{section_list}\n\n"
            "Relevant section numbers:"
        )

        # Use a small manifest to call the model
        from uuid import uuid4

        from lattice_jit.contracts import (
            CompiledContextItem,
            CompiledContextManifest,
            CompiledContextRole,
            CompiledContextStatus,
            KnowledgeNode,
            NodeType,
            PolicyBundle,
        )

        dummy_node = KnowledgeNode(
            tenant_id=uuid4(), node_type=NodeType.SECTION,
            title="rerank", content_hash="rerank", serving_confidence=1.0,
        )
        dummy_manifest = CompiledContextManifest(
            tenant_id=uuid4(), query_hash="rerank",
            policy_bundle_id=uuid4(), context_hash="rerank",
            budget_tokens=1000, actual_tokens=50,
            status=CompiledContextStatus.ACTIVE,
            items=[CompiledContextItem(
                tenant_id=uuid4(), manifest_id=uuid4(),
                ordinal=0, node_id=dummy_node.node_id,
                role=CompiledContextRole.EVIDENCE,
                token_count=50, score=1.0, snippet=section_list,
            )],
        )
        dummy_policy = PolicyBundle(
            tenant_id=uuid4(), query_class="general",
            tool_allowlist=[], redaction_rules=[], max_tokens=4000,
            phase_b_required=False, human_gate_required=False,
            opa_decision_hash="rerank",
        )

        answer = model_provider.generate(prompt, dummy_manifest, [dummy_node], dummy_policy)
        import re
        numbers = [int(n) for n in re.findall(r"\d+", answer) if 1 <= int(n) <= len(sections)]

        if not numbers:
            return None

        selected_indices = {n - 1 for n in numbers}
        return [node for idx, node in enumerate(nodes) if idx in selected_indices]
    except Exception:
        return None


# ── Fix 4: Metrics Question Decomposition ──────────────────────────────────


METRICS_KEYWORDS = (
    "ratio", "margin", "DPO", "DSO", "DIO", "turnover",
    "return on", "ROE", "ROA", "growth", "change in",
    "percent", "percentage", "basis points", "bps",
    "calculate", "compute", "per share",
)


def _is_metrics_question(query: str) -> bool:
    return any(kw.lower() in query.lower() for kw in METRICS_KEYWORDS)


def _decompose_metrics_query(query: str) -> str:
    """Decompose a metrics question to help the model extract needed values first.

    Adds instructions to identify the values needed for computation
    before answering the question.
    """
    return (
        f"{query}\n\n"
        "[Instructions: First identify the specific values needed to answer this question "
        "from the context. If a computation is required, show the formula and the values "
        "used. If the exact values are not in the context, state so clearly.]"
    )
