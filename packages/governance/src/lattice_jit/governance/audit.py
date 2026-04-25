from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from lattice_jit.contracts import AuditEvent
from lattice_jit.storage import StorageRepository


@dataclass(slots=True)
class AuditService:
    repository: StorageRepository

    def record(
        self,
        *,
        tenant_id: UUID,
        event_type: str,
        resource_type: str,
        resource_id: UUID | None = None,
        payload: dict[str, str | int | float | bool | None] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=payload or {},
        )
        self.repository.store_audit_event(event)
        return event

    def list_events(self, tenant_id: UUID) -> list[AuditEvent]:
        return self.repository.list_audit_events(tenant_id)
