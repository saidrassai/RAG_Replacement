from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import ClassVar

from lattice_jit.contracts import ReviewItem, ReviewRiskLevel
from lattice_jit.storage import StorageRepository


@dataclass(slots=True)
class LoadSheddingService:
    repository: StorageRepository
    enabled: bool = False
    max_items_per_minute: int = 100
    window_seconds: int = 60

    _timestamps: ClassVar[dict[str, list[float]]] = {}
    _rng: ClassVar[random.Random] = random.Random(42)

    def queue(self, candidate: ReviewItem) -> ReviewItem:
        existing = self.repository.get_review_item_by_fingerprint(
            candidate.tenant_id,
            candidate.fact_fingerprint,
        )
        if existing is None:
            if self._should_sample(candidate.tenant_id, candidate.risk_level, candidate.sample_rate):
                self.repository.upsert_review_item(candidate)
                return candidate
            return candidate

        merged = existing.model_copy(
            update={
                "dedup_count": existing.dedup_count + candidate.dedup_count,
                "evidence_count": existing.evidence_count + candidate.evidence_count,
                "risk_level": _max_risk(existing.risk_level, candidate.risk_level),
                "sample_rate": max(existing.sample_rate, candidate.sample_rate),
            }
        )
        self.repository.upsert_review_item(merged)
        return merged

    def _should_sample(
        self,
        tenant_id: object,
        risk_level: ReviewRiskLevel,
        sample_rate: float,
    ) -> bool:
        if not self.enabled:
            return True
        if sample_rate >= 1.0:
            return True

        if risk_level == ReviewRiskLevel.HIGH:
            return True

        if risk_level == ReviewRiskLevel.LOW:
            accept_probability = sample_rate
        else:
            accept_probability = sample_rate + (1.0 - sample_rate) * 0.5

        if not self._within_rate_limit(str(tenant_id)):
            accept_probability *= 0.1

        return self._rng.random() < accept_probability

    def _within_rate_limit(self, tenant_key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        timestamps = self._timestamps.setdefault(tenant_key, [])
        timestamps[:] = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= self.max_items_per_minute:
            return False
        timestamps.append(now)
        return True


def _max_risk(current: ReviewRiskLevel, incoming: ReviewRiskLevel) -> ReviewRiskLevel:
    rank = {
        ReviewRiskLevel.LOW: 0,
        ReviewRiskLevel.MEDIUM: 1,
        ReviewRiskLevel.HIGH: 2,
    }
    return current if rank[current] >= rank[incoming] else incoming
