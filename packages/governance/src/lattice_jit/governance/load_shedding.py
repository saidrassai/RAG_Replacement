from __future__ import annotations

from dataclasses import dataclass

from lattice_jit.contracts import ReviewItem, ReviewRiskLevel
from lattice_jit.storage import StorageRepository


@dataclass(slots=True)
class LoadSheddingService:
    repository: StorageRepository

    def queue(self, candidate: ReviewItem) -> ReviewItem:
        existing = self.repository.get_review_item_by_fingerprint(
            candidate.tenant_id,
            candidate.fact_fingerprint,
        )
        if existing is None:
            self.repository.upsert_review_item(candidate)
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


def _max_risk(current: ReviewRiskLevel, incoming: ReviewRiskLevel) -> ReviewRiskLevel:
    rank = {
        ReviewRiskLevel.LOW: 0,
        ReviewRiskLevel.MEDIUM: 1,
        ReviewRiskLevel.HIGH: 2,
    }
    return current if rank[current] >= rank[incoming] else incoming
