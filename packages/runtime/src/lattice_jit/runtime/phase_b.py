from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from celery import Celery
from lattice_jit.contracts import AnswerEnvelope, AnswerPhase, AnswerStatus
from lattice_jit.core import utcnow
from lattice_jit.storage import StorageRepository


class PhaseBScheduler(Protocol):
    def schedule(self, answer_id: UUID) -> str:
        ...


@dataclass(slots=True)
class PhaseBService:
    repository: StorageRepository

    def verify(self, answer_id: UUID) -> AnswerEnvelope | None:
        latest = self.repository.get_latest_answer(answer_id)
        if latest is None:
            return None
        if latest.phase == AnswerPhase.B:
            return latest

        verified = latest.model_copy(
            update={
                "phase": AnswerPhase.B,
                "status": AnswerStatus.COMPLETE,
                "provisional": False,
                "answer_text": (
                    f"{latest.answer_text}\n\nPhase B verification: placeholder verification completed."
                ),
                "phase_b_status": "complete",
                "created_at": utcnow(),
            }
        )
        self.repository.store_answer_event(verified)
        return verified


@dataclass(slots=True)
class InlinePhaseBScheduler:
    service: PhaseBService

    def schedule(self, answer_id: UUID) -> str:
        verified = self.service.verify(answer_id)
        return "complete" if verified is not None else "failed"


@dataclass(slots=True)
class NoopPhaseBScheduler:
    def schedule(self, answer_id: UUID) -> str:
        del answer_id
        return "queued"


@dataclass(slots=True)
class CeleryPhaseBScheduler:
    celery_app: Celery

    def schedule(self, answer_id: UUID) -> str:
        self.celery_app.send_task("lattice_jit.phase_b.verify", args=[str(answer_id)])
        return "queued"
