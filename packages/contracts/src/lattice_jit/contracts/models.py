from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .types import (
    AnswerPhase,
    AnswerStatus,
    CompiledContextRole,
    CompiledContextStatus,
    ConfidenceBand,
    EdgeType,
    NodeType,
    ReviewRiskLevel,
    ReviewState,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class KnowledgeNode(BaseModel):
    tenant_id: UUID
    node_id: UUID = Field(default_factory=uuid4)
    snapshot_id: UUID | None = None
    node_type: NodeType
    title: str
    source_uri: str | None = None
    body_ptr: str | None = None
    body_text: str | None = None
    content_hash: str
    snapshot_ref: str | None = None
    source_confidence: float = 1.0
    serving_confidence: float = 1.0
    volatility_score: float = 0.5
    freshness_expires_at: datetime | None = None
    review_state: ReviewState = ReviewState.NONE
    derived_from_run_id: UUID | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class KnowledgeEdge(BaseModel):
    tenant_id: UUID
    edge_id: UUID = Field(default_factory=uuid4)
    from_node_id: UUID
    to_node_id: UUID
    edge_type: EdgeType
    evidence_spans: list[dict[str, int | str]] = Field(default_factory=list)
    source_confidence: float = 1.0
    serving_confidence: float = 1.0
    active: bool = True
    cycle_break_reason: str | None = None
    created_by_run_id: UUID | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class PolicyBundle(BaseModel):
    policy_bundle_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    query_class: str
    tool_allowlist: list[str]
    redaction_rules: list[str]
    max_tokens: int
    phase_b_required: bool
    human_gate_required: bool
    opa_decision_hash: str
    created_at: datetime = Field(default_factory=_utcnow)


class CompiledContextItem(BaseModel):
    manifest_id: UUID
    ordinal: int
    node_id: UUID
    role: CompiledContextRole
    token_count: int
    score: float
    snippet: str


class CompiledContextManifest(BaseModel):
    manifest_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    query_hash: str
    policy_bundle_id: UUID
    context_hash: str
    budget_tokens: int
    actual_tokens: int
    status: CompiledContextStatus
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime | None = None
    items: list[CompiledContextItem] = Field(default_factory=list)


class ProvenanceRef(BaseModel):
    node_id: UUID
    title: str
    source_uri: str | None = None
    snapshot_id: UUID | None = None
    snapshot_ref: str | None = None
    content_hash: str
    score: float
    snippet: str


class AnswerEnvelope(BaseModel):
    answer_id: UUID
    tenant_id: UUID
    phase: AnswerPhase
    status: AnswerStatus
    answer_text: str
    confidence_band: ConfidenceBand
    provisional: bool
    provenance: list[ProvenanceRef] = Field(default_factory=list)
    conflict_flags: list[str] = Field(default_factory=list)
    manifest_id: UUID | None = None
    phase_b_status: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class ReviewItem(BaseModel):
    review_item_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    fact_fingerprint: str
    fact_type: str
    canonical_node_id: UUID | None = None
    dedup_count: int = 1
    risk_level: ReviewRiskLevel = ReviewRiskLevel.LOW
    review_state: ReviewState = ReviewState.PENDING
    sample_rate: float = 0.0
    evidence_count: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    reviewed_at: datetime | None = None


class FeedbackLabel(BaseModel):
    label_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    target_type: str
    target_id: UUID
    label_type: str
    label_value: float
    labeled_at: datetime = Field(default_factory=_utcnow)


class AuditEvent(BaseModel):
    audit_event_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    event_type: str
    resource_type: str
    resource_id: UUID | None = None
    payload: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
