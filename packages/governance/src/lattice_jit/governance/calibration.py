from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from lattice_jit.contracts import FeedbackLabel
from lattice_jit.core import utcnow
from lattice_jit.storage import StorageRepository


@dataclass(slots=True)
class CalibrationService:
    repository: StorageRepository

    def record_feedback(
        self,
        *,
        tenant_id: UUID,
        target_type: str,
        target_id: UUID,
        label_type: str,
        label_value: float,
    ) -> FeedbackLabel:
        label = FeedbackLabel(
            tenant_id=tenant_id,
            target_type=target_type,
            target_id=target_id,
            label_type=label_type,
            label_value=label_value,
            labeled_at=utcnow(),
        )
        self.repository.store_feedback_label(
            tenant_id=label.tenant_id,
            target_type=label.target_type,
            target_id=label.target_id,
            label_type=label.label_type,
            label_value=label.label_value,
            labeled_at=label.labeled_at,
        )
        return label

    def list_feedback(self, tenant_id: UUID) -> list[FeedbackLabel]:
        return self.repository.list_feedback_labels(tenant_id)
