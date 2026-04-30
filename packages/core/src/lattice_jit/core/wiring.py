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
    from lattice_jit.policy import build_policy_evaluator
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
    load_shedding_service = LoadSheddingService(
        repository,
        enabled=resolved_settings.load_shedding_enabled,
        max_items_per_minute=resolved_settings.load_shedding_max_items_per_minute,
        window_seconds=resolved_settings.load_shedding_window_seconds,
    )
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

    embedding_service: object | None = None
    if resolved_settings.embedding_enabled:
        from lattice_jit.runtime.embedding import EmbeddingService

        embedding_service = EmbeddingService(
            model_name=resolved_settings.embedding_model,
            enabled=True,
        )

    query_service = QueryService(
        repository=repository,
        router=SemanticRouter(
            max_nodes=resolved_settings.router_max_nodes,
            mode=resolved_settings.router_mode,
            backend_kwargs=(
                {"embedding_service": embedding_service}
                if embedding_service is not None
                else {}
            ),
        ),
        compiler=compiler,
        policy_evaluator=build_policy_evaluator(
            _policy_evaluator_config(
                mode=resolved_settings.policy_mode,
                opa_url=resolved_settings.policy_opa_url,
                opa_policy_path=resolved_settings.policy_opa_path,
                opa_timeout_seconds=resolved_settings.policy_opa_timeout_seconds,
                opa_fail_closed=resolved_settings.policy_opa_fail_closed,
            )
        ),
        model_provider=_select_model_provider(
            resolved_settings,
        ),
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


def _select_model_provider(settings: Settings):
    from lattice_jit.model_proxy import ModelProviderConfig, build_model_provider

    return build_model_provider(
        ModelProviderConfig(
            provider=settings.model_provider,
            litellm_model=settings.litellm_model,
            litellm_temperature=settings.litellm_temperature,
            litellm_max_output_tokens=settings.litellm_max_output_tokens,
            deepseek_api_key=settings.litellm_deepseek_api_key,
            deepseek_base_url=settings.litellm_deepseek_base_url,
            prompt_caching_enabled=settings.litellm_prompt_caching_enabled,
            huggingface_model=settings.huggingface_model,
        )
    )


def _policy_evaluator_config(
    mode: str,
    opa_url: str,
    opa_policy_path: str,
    opa_timeout_seconds: float,
    opa_fail_closed: bool = False,
):
    from lattice_jit.policy import PolicyEvaluatorConfig

    return PolicyEvaluatorConfig(
        mode=mode,
        opa_url=opa_url,
        opa_policy_path=opa_policy_path,
        opa_timeout_seconds=opa_timeout_seconds,
        opa_fail_closed=opa_fail_closed,
    )


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
