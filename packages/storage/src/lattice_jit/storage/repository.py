from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from lattice_jit.contracts import (
    AnswerEnvelope,
    AnswerPhase,
    AnswerStatus,
    AuditEvent,
    CompiledContextItem,
    CompiledContextManifest,
    CompiledContextRole,
    CompiledContextStatus,
    ConfidenceBand,
    EdgeType,
    FeedbackLabel,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    PolicyBundle,
    ProvenanceRef,
    ReviewItem,
    ReviewRiskLevel,
    ReviewState,
    SnapshotStatus,
)
from sqlalchemy import delete, desc, select, update
from sqlalchemy.orm import Session

from .db import Database
from .orm import (
    AnswerEventOrm,
    AuditEventOrm,
    CompiledContextItemOrm,
    CompiledContextManifestOrm,
    FeedbackLabelOrm,
    KnowledgeEdgeOrm,
    KnowledgeNodeOrm,
    PolicyBundleOrm,
    ReviewQueueOrm,
    SourceSnapshotOrm,
)


@dataclass(slots=True)
class SourceSnapshotRecord:
    snapshot_id: UUID
    tenant_id: UUID
    repo_path: str
    git_ref: str | None
    include_globs: list[str]
    exclude_globs: list[str]
    status: SnapshotStatus
    root_node_id: UUID | None
    created_at: datetime


class StorageRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_schema(self) -> None:
        self.database.create_schema()

    def create_source_snapshot(self, record: SourceSnapshotRecord) -> SourceSnapshotRecord:
        with self.database.session() as session:
            session.add(
                SourceSnapshotOrm(
                    snapshot_id=record.snapshot_id,
                    tenant_id=record.tenant_id,
                    repo_path=record.repo_path,
                    git_ref=record.git_ref,
                    include_globs=record.include_globs,
                    exclude_globs=record.exclude_globs,
                    status=record.status.value,
                    root_node_id=record.root_node_id,
                    created_at=record.created_at,
                )
            )
        return record

    def mark_snapshot_completed(self, snapshot_id: UUID, root_node_id: UUID) -> None:
        with self.database.session() as session:
            session.execute(
                update(SourceSnapshotOrm)
                .where(SourceSnapshotOrm.snapshot_id == snapshot_id)
                .values(status=SnapshotStatus.COMPLETED.value, root_node_id=root_node_id)
            )

    def get_source_snapshot(self, snapshot_id: UUID) -> SourceSnapshotRecord | None:
        with self.database.session() as session:
            orm = session.get(SourceSnapshotOrm, snapshot_id)
            if orm is None:
                return None
            return SourceSnapshotRecord(
                snapshot_id=orm.snapshot_id,
                tenant_id=orm.tenant_id,
                repo_path=orm.repo_path,
                git_ref=orm.git_ref,
                include_globs=list(orm.include_globs),
                exclude_globs=list(orm.exclude_globs),
                status=SnapshotStatus(orm.status),
                root_node_id=orm.root_node_id,
                created_at=orm.created_at,
            )

    def get_latest_snapshot(self, tenant_id: UUID) -> SourceSnapshotRecord | None:
        with self.database.session() as session:
            orm = session.scalar(
                select(SourceSnapshotOrm)
                .where(SourceSnapshotOrm.tenant_id == tenant_id)
                .order_by(desc(SourceSnapshotOrm.created_at))
            )
            if orm is None:
                return None
            return SourceSnapshotRecord(
                snapshot_id=orm.snapshot_id,
                tenant_id=orm.tenant_id,
                repo_path=orm.repo_path,
                git_ref=orm.git_ref,
                include_globs=list(orm.include_globs),
                exclude_globs=list(orm.exclude_globs),
                status=SnapshotStatus(orm.status),
                root_node_id=orm.root_node_id,
                created_at=orm.created_at,
            )

    def get_node(self, node_id: UUID) -> KnowledgeNode | None:
        with self.database.session() as session:
            orm = session.get(KnowledgeNodeOrm, node_id)
            if orm is None:
                return None
            return self._to_node(orm)

    def upsert_nodes(self, nodes: Iterable[KnowledgeNode]) -> None:
        with self.database.session() as session:
            for node in nodes:
                session.merge(
                    KnowledgeNodeOrm(
                        node_id=node.node_id,
                        tenant_id=node.tenant_id,
                        snapshot_id=node.snapshot_id,
                        node_type=node.node_type.value,
                        title=node.title,
                        source_uri=node.source_uri,
                        body_ptr=node.body_ptr,
                        body_text=node.body_text,
                        content_hash=node.content_hash,
                        snapshot_ref=node.snapshot_ref,
                        source_confidence=node.source_confidence,
                        serving_confidence=node.serving_confidence,
                        volatility_score=node.volatility_score,
                        freshness_expires_at=node.freshness_expires_at,
                        review_state=node.review_state.value,
                        derived_from_run_id=node.derived_from_run_id,
                        metadata_json=node.metadata,
                        created_at=node.created_at,
                        updated_at=node.updated_at,
                    )
                )

    def upsert_edges(self, edges: Iterable[KnowledgeEdge]) -> None:
        with self.database.session() as session:
            for edge in edges:
                session.merge(
                    KnowledgeEdgeOrm(
                        edge_id=edge.edge_id,
                        tenant_id=edge.tenant_id,
                        from_node_id=edge.from_node_id,
                        to_node_id=edge.to_node_id,
                        edge_type=edge.edge_type.value,
                        evidence_spans=edge.evidence_spans,
                        source_confidence=edge.source_confidence,
                        serving_confidence=edge.serving_confidence,
                        active=edge.active,
                        cycle_break_reason=edge.cycle_break_reason,
                        created_by_run_id=edge.created_by_run_id,
                        created_at=edge.created_at,
                    )
                )

    def list_snapshot_nodes(self, snapshot_id: UUID) -> list[KnowledgeNode]:
        with self.database.session() as session:
            rows = session.scalars(
                select(KnowledgeNodeOrm)
                .where(KnowledgeNodeOrm.snapshot_id == snapshot_id)
                .order_by(KnowledgeNodeOrm.created_at.asc())
            ).all()
            return [self._to_node(row) for row in rows]

    def get_nodes_by_ids(self, node_ids: Iterable[UUID]) -> list[KnowledgeNode]:
        node_id_list = list(node_ids)
        if not node_id_list:
            return []
        with self.database.session() as session:
            rows = session.scalars(
                select(KnowledgeNodeOrm).where(KnowledgeNodeOrm.node_id.in_(node_id_list))
            ).all()
            by_id = {row.node_id: self._to_node(row) for row in rows}
            return [by_id[node_id] for node_id in node_id_list if node_id in by_id]

    def list_nodes_for_tenant(self, tenant_id: UUID) -> list[KnowledgeNode]:
        with self.database.session() as session:
            rows = session.scalars(
                select(KnowledgeNodeOrm)
                .where(KnowledgeNodeOrm.tenant_id == tenant_id)
                .order_by(KnowledgeNodeOrm.created_at.asc())
            ).all()
            return [self._to_node(row) for row in rows]

    def list_edges_for_nodes(self, node_ids: Iterable[UUID]) -> list[KnowledgeEdge]:
        node_id_list = list(node_ids)
        if not node_id_list:
            return []
        with self.database.session() as session:
            rows = session.scalars(
                select(KnowledgeEdgeOrm).where(
                    KnowledgeEdgeOrm.from_node_id.in_(node_id_list)
                    | KnowledgeEdgeOrm.to_node_id.in_(node_id_list)
                )
            ).all()
            return [self._to_edge(row) for row in rows]

    def store_policy_bundle(self, bundle: PolicyBundle) -> None:
        with self.database.session() as session:
            session.merge(
                PolicyBundleOrm(
                    policy_bundle_id=bundle.policy_bundle_id,
                    tenant_id=bundle.tenant_id,
                    query_class=bundle.query_class,
                    tool_allowlist=bundle.tool_allowlist,
                    redaction_rules=bundle.redaction_rules,
                    max_tokens=bundle.max_tokens,
                    phase_b_required=bundle.phase_b_required,
                    human_gate_required=bundle.human_gate_required,
                    opa_decision_hash=bundle.opa_decision_hash,
                    created_at=bundle.created_at,
                )
            )

    def find_manifest_by_query_hash(self, tenant_id: UUID, query_hash: str) -> CompiledContextManifest | None:
        with self.database.session() as session:
            orm = session.scalar(
                select(CompiledContextManifestOrm)
                .where(
                    CompiledContextManifestOrm.tenant_id == tenant_id,
                    CompiledContextManifestOrm.query_hash == query_hash,
                    CompiledContextManifestOrm.status == "active",
                )
                .order_by(desc(CompiledContextManifestOrm.created_at))
            )
            if orm is None:
                return None
            return self._manifest_with_items(session, orm)

    def store_manifest(self, manifest: CompiledContextManifest) -> None:
        with self.database.session() as session:
            session.merge(
                CompiledContextManifestOrm(
                    manifest_id=manifest.manifest_id,
                    tenant_id=manifest.tenant_id,
                    query_hash=manifest.query_hash,
                    policy_bundle_id=manifest.policy_bundle_id,
                    context_hash=manifest.context_hash,
                    budget_tokens=manifest.budget_tokens,
                    actual_tokens=manifest.actual_tokens,
                    status=manifest.status.value,
                    created_at=manifest.created_at,
                    expires_at=manifest.expires_at,
                )
            )
            session.execute(
                delete(CompiledContextItemOrm).where(
                    CompiledContextItemOrm.manifest_id == manifest.manifest_id
                )
            )
            for item in manifest.items:
                session.add(
                    CompiledContextItemOrm(
                        tenant_id=manifest.tenant_id,
                        manifest_id=item.manifest_id,
                        ordinal=item.ordinal,
                        node_id=item.node_id,
                        role=item.role.value,
                        token_count=item.token_count,
                        score=item.score,
                        snippet=item.snippet,
                    )
                )

    def get_manifest(self, manifest_id: UUID) -> CompiledContextManifest | None:
        with self.database.session() as session:
            orm = session.get(CompiledContextManifestOrm, manifest_id)
            if orm is None:
                return None
            return self._manifest_with_items(session, orm)

    def invalidate_manifest(self, manifest_id: UUID) -> CompiledContextManifest | None:
        with self.database.session() as session:
            orm = session.get(CompiledContextManifestOrm, manifest_id)
            if orm is None:
                return None
            orm.status = "invalidated"
            return self._manifest_with_items(session, orm)

    def store_answer_event(self, envelope: AnswerEnvelope) -> None:
        with self.database.session() as session:
            session.add(
                AnswerEventOrm(
                    event_id=uuid4(),
                    answer_id=envelope.answer_id,
                    tenant_id=envelope.tenant_id,
                    phase=envelope.phase.value,
                    status=envelope.status.value,
                    answer_text=envelope.answer_text,
                    confidence_band=envelope.confidence_band.value,
                    provisional=envelope.provisional,
                    provenance_json=[item.model_dump(mode="json") for item in envelope.provenance],
                    conflict_flags_json=envelope.conflict_flags,
                    manifest_id=envelope.manifest_id,
                    phase_b_status=envelope.phase_b_status,
                    created_at=envelope.created_at,
                )
            )

    def get_latest_answer(self, answer_id: UUID) -> AnswerEnvelope | None:
        with self.database.session() as session:
            orm = session.scalar(
                select(AnswerEventOrm)
                .where(AnswerEventOrm.answer_id == answer_id)
                .order_by(desc(AnswerEventOrm.created_at))
            )
            if orm is None:
                return None
            return self._to_answer(orm)

    def list_answer_events(self, answer_id: UUID) -> list[AnswerEnvelope]:
        with self.database.session() as session:
            rows = session.scalars(
                select(AnswerEventOrm)
                .where(AnswerEventOrm.answer_id == answer_id)
                .order_by(AnswerEventOrm.created_at.asc())
            ).all()
            return [self._to_answer(row) for row in rows]

    def update_phase_a_phase_b_status(self, answer_id: UUID, phase_b_status: str) -> None:
        with self.database.session() as session:
            orm = session.scalar(
                select(AnswerEventOrm)
                .where(
                    AnswerEventOrm.answer_id == answer_id,
                    AnswerEventOrm.phase == "A",
                )
                .order_by(desc(AnswerEventOrm.created_at))
            )
            if orm is not None:
                orm.phase_b_status = phase_b_status

    def upsert_review_item(self, item: ReviewItem) -> None:
        with self.database.session() as session:
            session.merge(
                ReviewQueueOrm(
                    review_item_id=item.review_item_id,
                    tenant_id=item.tenant_id,
                    fact_fingerprint=item.fact_fingerprint,
                    fact_type=item.fact_type,
                    canonical_node_id=item.canonical_node_id,
                    dedup_count=item.dedup_count,
                    risk_level=item.risk_level.value,
                    review_state=item.review_state.value,
                    sample_rate=item.sample_rate,
                    evidence_count=item.evidence_count,
                    created_at=item.created_at,
                    reviewed_at=item.reviewed_at,
                )
            )

    def get_review_item_by_fingerprint(self, tenant_id: UUID, fact_fingerprint: str) -> ReviewItem | None:
        with self.database.session() as session:
            orm = session.scalar(
                select(ReviewQueueOrm)
                .where(
                    ReviewQueueOrm.tenant_id == tenant_id,
                    ReviewQueueOrm.fact_fingerprint == fact_fingerprint,
                )
                .order_by(desc(ReviewQueueOrm.created_at))
            )
            if orm is None:
                return None
            return self._to_review_item(orm)

    def list_review_items(self, tenant_id: UUID) -> list[ReviewItem]:
        with self.database.session() as session:
            rows = session.scalars(
                select(ReviewQueueOrm)
                .where(ReviewQueueOrm.tenant_id == tenant_id)
                .order_by(ReviewQueueOrm.created_at.asc())
            ).all()
            return [self._to_review_item(row) for row in rows]

    def get_review_item(self, review_item_id: UUID, tenant_id: UUID) -> ReviewItem | None:
        with self.database.session() as session:
            orm = session.get(ReviewQueueOrm, review_item_id)
            if orm is None or orm.tenant_id != tenant_id:
                return None
            return self._to_review_item(orm)

    def update_review_item_state(
        self, review_item_id: UUID, tenant_id: UUID, review_state: ReviewState, reviewed_at: datetime
    ) -> ReviewItem | None:
        with self.database.session() as session:
            orm = session.get(ReviewQueueOrm, review_item_id)
            if orm is None or orm.tenant_id != tenant_id:
                return None
            orm.review_state = review_state.value
            orm.reviewed_at = reviewed_at
            return self._to_review_item(orm)

    def store_feedback_label(
        self,
        tenant_id: UUID,
        target_type: str,
        target_id: UUID,
        label_type: str,
        label_value: float,
        labeled_at: datetime,
    ) -> None:
        with self.database.session() as session:
            session.add(
                FeedbackLabelOrm(
                    label_id=uuid4(),
                    tenant_id=tenant_id,
                    target_type=target_type,
                    target_id=target_id,
                    label_type=label_type,
                    label_value=label_value,
                    labeled_at=labeled_at,
                )
            )

    def list_feedback_labels(self, tenant_id: UUID) -> list[FeedbackLabel]:
        with self.database.session() as session:
            rows = session.scalars(
                select(FeedbackLabelOrm)
                .where(FeedbackLabelOrm.tenant_id == tenant_id)
                .order_by(FeedbackLabelOrm.labeled_at.asc())
            ).all()
            return [
                FeedbackLabel(
                    label_id=row.label_id,
                    tenant_id=row.tenant_id,
                    target_type=row.target_type,
                    target_id=row.target_id,
                    label_type=row.label_type,
                    label_value=row.label_value,
                    labeled_at=row.labeled_at,
                )
                for row in rows
            ]

    def store_audit_event(self, event: AuditEvent) -> None:
        with self.database.session() as session:
            session.add(
                AuditEventOrm(
                    audit_event_id=event.audit_event_id,
                    tenant_id=event.tenant_id,
                    event_type=event.event_type,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    payload_json=event.payload,
                    created_at=event.created_at,
                )
            )

    def list_audit_events(self, tenant_id: UUID) -> list[AuditEvent]:
        with self.database.session() as session:
            rows = session.scalars(
                select(AuditEventOrm)
                .where(AuditEventOrm.tenant_id == tenant_id)
                .order_by(AuditEventOrm.created_at.asc())
            ).all()
            return [
                AuditEvent(
                    audit_event_id=row.audit_event_id,
                    tenant_id=row.tenant_id,
                    event_type=row.event_type,
                    resource_type=row.resource_type,
                    resource_id=row.resource_id,
                    payload=_payload_dict(row.payload_json or {}),
                    created_at=row.created_at,
                )
                for row in rows
            ]

    def list_audit_events_filtered(
        self,
        tenant_id: UUID,
        *,
        event_type: str | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> list[AuditEvent]:
        with self.database.session() as session:
            stmt = select(AuditEventOrm).where(AuditEventOrm.tenant_id == tenant_id)
            if event_type:
                stmt = stmt.where(AuditEventOrm.event_type == event_type)
            if resource_type:
                stmt = stmt.where(AuditEventOrm.resource_type == resource_type)
            if resource_id is not None:
                stmt = stmt.where(AuditEventOrm.resource_id == resource_id)
            order = desc(AuditEventOrm.created_at) if sort_desc else AuditEventOrm.created_at.asc()
            stmt = stmt.order_by(order).offset(offset).limit(limit)
            rows = session.scalars(stmt).all()
            return [
                AuditEvent(
                    audit_event_id=row.audit_event_id,
                    tenant_id=row.tenant_id,
                    event_type=row.event_type,
                    resource_type=row.resource_type,
                    resource_id=row.resource_id,
                    payload=_payload_dict(row.payload_json or {}),
                    created_at=row.created_at,
                )
                for row in rows
            ]

    def count_audit_events(
        self,
        tenant_id: UUID,
        *,
        event_type: str | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> int:
        with self.database.session() as session:
            stmt = select(AuditEventOrm).where(AuditEventOrm.tenant_id == tenant_id)
            if event_type:
                stmt = stmt.where(AuditEventOrm.event_type == event_type)
            if resource_type:
                stmt = stmt.where(AuditEventOrm.resource_type == resource_type)
            if resource_id is not None:
                stmt = stmt.where(AuditEventOrm.resource_id == resource_id)
            from sqlalchemy import func

            count_stmt = select(func.count()).select_from(stmt.subquery())
            result = session.scalar(count_stmt)
            return result or 0

    def _manifest_with_items(
        self,
        session: Session,
        orm: CompiledContextManifestOrm,
    ) -> CompiledContextManifest:
        items = session.scalars(
            select(CompiledContextItemOrm)
            .where(CompiledContextItemOrm.manifest_id == orm.manifest_id)
            .order_by(CompiledContextItemOrm.ordinal.asc())
        ).all()
        return CompiledContextManifest(
            manifest_id=orm.manifest_id,
            tenant_id=orm.tenant_id,
            query_hash=orm.query_hash,
            policy_bundle_id=orm.policy_bundle_id,
            context_hash=orm.context_hash,
            budget_tokens=orm.budget_tokens,
            actual_tokens=orm.actual_tokens,
            status=CompiledContextStatus(orm.status),
            created_at=orm.created_at,
            expires_at=orm.expires_at,
            items=[
                CompiledContextItem(
                    tenant_id=item.tenant_id,
                    manifest_id=item.manifest_id,
                    ordinal=item.ordinal,
                    node_id=item.node_id,
                    role=CompiledContextRole(item.role),
                    token_count=item.token_count,
                    score=item.score,
                    snippet=item.snippet,
                )
                for item in items
            ],
        )

    def _to_node(self, orm: KnowledgeNodeOrm) -> KnowledgeNode:
        return KnowledgeNode(
            tenant_id=orm.tenant_id,
            node_id=orm.node_id,
            snapshot_id=orm.snapshot_id,
            node_type=NodeType(orm.node_type),
            title=orm.title,
            source_uri=orm.source_uri,
            body_ptr=orm.body_ptr,
            body_text=orm.body_text,
            content_hash=orm.content_hash,
            snapshot_ref=orm.snapshot_ref,
            source_confidence=orm.source_confidence,
            serving_confidence=orm.serving_confidence,
            volatility_score=orm.volatility_score,
            freshness_expires_at=orm.freshness_expires_at,
            review_state=ReviewState(orm.review_state),
            derived_from_run_id=orm.derived_from_run_id,
            metadata=_payload_dict(orm.metadata_json or {}),
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _to_edge(self, orm: KnowledgeEdgeOrm) -> KnowledgeEdge:
        return KnowledgeEdge(
            tenant_id=orm.tenant_id,
            edge_id=orm.edge_id,
            from_node_id=orm.from_node_id,
            to_node_id=orm.to_node_id,
            edge_type=EdgeType(orm.edge_type),
            evidence_spans=_evidence_spans(orm.evidence_spans or []),
            source_confidence=orm.source_confidence,
            serving_confidence=orm.serving_confidence,
            active=orm.active,
            cycle_break_reason=orm.cycle_break_reason,
            created_by_run_id=orm.created_by_run_id,
            created_at=orm.created_at,
        )

    def _to_answer(self, orm: AnswerEventOrm) -> AnswerEnvelope:
        return AnswerEnvelope(
            answer_id=orm.answer_id,
            tenant_id=orm.tenant_id,
            phase=AnswerPhase(orm.phase),
            status=AnswerStatus(orm.status),
            answer_text=orm.answer_text,
            confidence_band=ConfidenceBand(orm.confidence_band),
            provisional=orm.provisional,
            provenance=[ProvenanceRef.model_validate(item) for item in orm.provenance_json or []],
            conflict_flags=list(orm.conflict_flags_json or []),
            manifest_id=orm.manifest_id,
            phase_b_status=orm.phase_b_status,
            created_at=orm.created_at,
        )

    def _to_review_item(self, orm: ReviewQueueOrm) -> ReviewItem:
        return ReviewItem(
            review_item_id=orm.review_item_id,
            tenant_id=orm.tenant_id,
            fact_fingerprint=orm.fact_fingerprint,
            fact_type=orm.fact_type,
            canonical_node_id=orm.canonical_node_id,
            dedup_count=orm.dedup_count,
            risk_level=ReviewRiskLevel(orm.risk_level),
            review_state=ReviewState(orm.review_state),
            sample_rate=orm.sample_rate,
            evidence_count=orm.evidence_count,
            created_at=orm.created_at,
            reviewed_at=orm.reviewed_at,
        )


def _payload_dict(
    value: Mapping[str, object],
) -> dict[str, str | int | float | bool | None]:
    return {
        key: cast(str | int | float | bool | None, item)
        for key, item in value.items()
    }


def _evidence_spans(value: list[dict[str, object]]) -> list[dict[str, int | str]]:
    return [
        {
            key: cast(int | str, item)
            for key, item in span.items()
        }
        for span in value
    ]
