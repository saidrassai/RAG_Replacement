from enum import StrEnum


class NodeType(StrEnum):
    SOURCE = "source"
    SECTION = "section"
    DECISION = "decision"
    CONSTRAINT = "constraint"
    API_SIGNATURE = "api_signature"
    OWNER = "owner"
    INCIDENT = "incident"
    SYNTHESIS = "synthesis"


class EdgeType(StrEnum):
    CITES = "cites"
    DEPENDS_ON = "depends_on"
    DERIVES_FROM = "derives_from"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"
    BELONGS_TO = "belongs_to"
    OWNED_BY = "owned_by"


class ReviewState(StrEnum):
    NONE = "none"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SAMPLED = "sampled"


class ReviewRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnswerPhase(StrEnum):
    A = "A"
    B = "B"


class AnswerStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class ConfidenceBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PhaseBMode(StrEnum):
    AUTO = "auto"
    OFF = "off"
    FORCE = "force"


class SnapshotStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class CompiledContextStatus(StrEnum):
    ACTIVE = "active"
    INVALIDATED = "invalidated"
    SUPERSEDED = "superseded"


class CompiledContextRole(StrEnum):
    POLICY_NOTICE = "policy_notice"
    BRIDGE = "bridge"
    SUMMARY = "summary"
    EVIDENCE = "evidence"
    SESSION_KERNEL = "session_kernel"
