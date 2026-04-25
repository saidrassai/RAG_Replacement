from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4


def generate_id() -> UUID:
    return uuid4()


def stable_hash(*parts: object) -> str:
    joined = "||".join(str(part) for part in parts)
    return sha256(joined.encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    return datetime.now(UTC)
