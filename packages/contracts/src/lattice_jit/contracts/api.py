from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from .models import AnswerEnvelope, ReviewItem
from .types import PhaseBMode, SnapshotStatus


class SnapshotGitRequest(BaseModel):
    tenant_id: UUID
    repo_path: str
    git_ref: str | None = None
    include_globs: list[str] = Field(default_factory=list)
    exclude_globs: list[str] = Field(default_factory=list)


class SnapshotResponse(BaseModel):
    tenant_id: UUID
    snapshot_id: UUID
    root_node_id: UUID
    status: SnapshotStatus


class QueryRequest(BaseModel):
    tenant_id: UUID
    query: str
    snapshot_id: UUID | None = None
    subgraph_ids: list[UUID] | None = None
    phase_b_mode: PhaseBMode = PhaseBMode.AUTO


class QueryResponse(BaseModel):
    answer_id: UUID
    phase_a: AnswerEnvelope
    phase_b_status: str
    manifest_id: UUID


class ReviewQueueResponse(BaseModel):
    items: list[ReviewItem]
