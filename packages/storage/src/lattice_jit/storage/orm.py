from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SourceSnapshotOrm(Base):
    __tablename__ = "source_snapshots"

    snapshot_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    repo_path: Mapped[str] = mapped_column(Text)
    git_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    include_globs: Mapped[list[str]] = mapped_column(JSON, default=list)
    exclude_globs: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32))
    root_node_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class KnowledgeNodeOrm(Base):
    __tablename__ = "knowledge_nodes"

    node_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("source_snapshots.snapshot_id"),
        nullable=True,
        index=True,
    )
    node_type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512))
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_ptr: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    snapshot_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_confidence: Mapped[float] = mapped_column(Float)
    serving_confidence: Mapped[float] = mapped_column(Float)
    volatility_score: Mapped[float] = mapped_column(Float)
    freshness_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_state: Mapped[str] = mapped_column(String(32))
    derived_from_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class KnowledgeEdgeOrm(Base):
    __tablename__ = "knowledge_edges"

    edge_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    from_node_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_nodes.node_id"), index=True)
    to_node_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_nodes.node_id"), index=True)
    edge_type: Mapped[str] = mapped_column(String(64), index=True)
    evidence_spans: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    source_confidence: Mapped[float] = mapped_column(Float)
    serving_confidence: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    cycle_break_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CompiledContextManifestOrm(Base):
    __tablename__ = "compiled_context_manifests"

    manifest_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    query_hash: Mapped[str] = mapped_column(String(64), index=True)
    policy_bundle_id: Mapped[UUID] = mapped_column(ForeignKey("policy_bundles.policy_bundle_id"))
    context_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    budget_tokens: Mapped[int] = mapped_column(Integer)
    actual_tokens: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CompiledContextItemOrm(Base):
    __tablename__ = "compiled_context_items"

    tenant_id: Mapped[UUID] = mapped_column(index=True)
    manifest_id: Mapped[UUID] = mapped_column(
        ForeignKey("compiled_context_manifests.manifest_id"),
        primary_key=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_nodes.node_id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    token_count: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    snippet: Mapped[str] = mapped_column(Text)


class PolicyBundleOrm(Base):
    __tablename__ = "policy_bundles"

    policy_bundle_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    query_class: Mapped[str] = mapped_column(String(128), index=True)
    tool_allowlist: Mapped[list[str]] = mapped_column(JSON, default=list)
    redaction_rules: Mapped[list[str]] = mapped_column(JSON, default=list)
    max_tokens: Mapped[int] = mapped_column(Integer)
    phase_b_required: Mapped[bool] = mapped_column(Boolean)
    human_gate_required: Mapped[bool] = mapped_column(Boolean)
    opa_decision_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AnswerEventOrm(Base):
    __tablename__ = "answer_events"

    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    answer_id: Mapped[UUID] = mapped_column(index=True)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    phase: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(32))
    answer_text: Mapped[str] = mapped_column(Text)
    confidence_band: Mapped[str] = mapped_column(String(16))
    provisional: Mapped[bool] = mapped_column(Boolean)
    provenance_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    conflict_flags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    manifest_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    phase_b_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReviewQueueOrm(Base):
    __tablename__ = "review_queue"

    review_item_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    fact_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    fact_type: Mapped[str] = mapped_column(String(128), index=True)
    canonical_node_id: Mapped[UUID | None] = mapped_column(nullable=True)
    dedup_count: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(16))
    review_state: Mapped[str] = mapped_column(String(32), index=True)
    sample_rate: Mapped[float] = mapped_column(Float)
    evidence_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FeedbackLabelOrm(Base):
    __tablename__ = "feedback_labels"

    label_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    target_type: Mapped[str] = mapped_column(String(32), index=True)
    target_id: Mapped[UUID] = mapped_column(index=True)
    label_type: Mapped[str] = mapped_column(String(32), index=True)
    label_value: Mapped[float] = mapped_column(Float)
    labeled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEventOrm(Base):
    __tablename__ = "audit_events"

    audit_event_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
