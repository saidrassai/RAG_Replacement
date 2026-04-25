from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .logging import configure_logging
from .settings import Settings, get_settings

if TYPE_CHECKING:
    from lattice_jit.connectors.git_local import GitLocalSnapshotService
    from lattice_jit.governance import AuditService, CalibrationService, GovernanceService, LoadSheddingService
    from lattice_jit.runtime import PhaseBService, QueryService
    from lattice_jit.storage import CacheStore, StorageRepository


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    repository: StorageRepository
    cache_store: CacheStore
    snapshot_service: GitLocalSnapshotService
    query_service: QueryService
    governance_service: GovernanceService
    phase_b_service: PhaseBService
    audit_service: AuditService
    calibration_service: CalibrationService
    load_shedding_service: LoadSheddingService


def build_container(settings: Settings | None = None, *, force_inline_phase_b: bool | None = None) -> AppContainer:
    from lattice_jit.connectors.git_local import GitLocalSnapshotService
    from lattice_jit.governance import (
        AuditService,
        CalibrationService,
        GovernanceService,
        LoadSheddingService,
    )
    from lattice_jit.policy import PolicyEvaluator
    from lattice_jit.runtime import (
        ContextCompiler,
        PhaseBService,
        QueryService,
        SemanticRouter,
    )
    from lattice_jit.storage import StorageRepository, build_cache_store, build_database

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    database = build_database(resolved_settings.database_url)
    repository = StorageRepository(database)
    repository.create_schema()

    cache_store = build_cache_store(resolved_settings.redis_url)
    audit_service = AuditService(repository)
    calibration_service = CalibrationService(repository)
    load_shedding_service = LoadSheddingService(repository)
    governance_service = GovernanceService(
        repository=repository,
        audit_service=audit_service,
        calibration_service=calibration_service,
        load_shedding_service=load_shedding_service,
    )
    phase_b_service = PhaseBService(repository)
    scheduler = _select_phase_b_scheduler(
        resolved_settings.celery_eager,
        force_inline_phase_b,
        phase_b_service,
        resolved_settings.celery_broker_url,
        resolved_settings.celery_result_backend,
    )
    snapshot_service = GitLocalSnapshotService(repository)
    compiler = ContextCompiler(repository, cache_store, resolved_settings)
    query_service = QueryService(
        repository=repository,
        router=SemanticRouter(),
        compiler=compiler,
        policy_evaluator=PolicyEvaluator(),
        model_provider=_select_model_provider(resolved_settings.model_provider),
        governance_service=governance_service,
        phase_b_scheduler=scheduler,
    )
    return AppContainer(
        settings=resolved_settings,
        repository=repository,
        cache_store=cache_store,
        snapshot_service=snapshot_service,
        query_service=query_service,
        governance_service=governance_service,
        phase_b_service=phase_b_service,
        audit_service=audit_service,
        calibration_service=calibration_service,
        load_shedding_service=load_shedding_service,
    )


def _select_model_provider(provider_name: str):
    from lattice_jit.model_proxy import LiteLLMModelProvider, StubModelProvider

    if provider_name == "litellm":
        return LiteLLMModelProvider()
    return StubModelProvider()


def _select_phase_b_scheduler(
    celery_eager: bool,
    force_inline_phase_b: bool | None,
    phase_b_service,
    broker_url: str,
    result_backend: str,
):
    from celery import Celery
    from lattice_jit.runtime import CeleryPhaseBScheduler, InlinePhaseBScheduler, NoopPhaseBScheduler

    if force_inline_phase_b is True:
        return InlinePhaseBScheduler(phase_b_service)
    if force_inline_phase_b is False:
        return NoopPhaseBScheduler()
    if celery_eager:
        return InlinePhaseBScheduler(phase_b_service)
    celery_app = Celery(
        "lattice_jit_scheduler",
        broker=broker_url,
        backend=result_backend,
    )
    return CeleryPhaseBScheduler(celery_app)
