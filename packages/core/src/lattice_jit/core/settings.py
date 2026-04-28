from __future__ import annotations

from functools import lru_cache
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LJIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "local"
    app_name: str = "Lattice-JIT Compiler"
    database_url: str = "sqlite+pysqlite:///:memory:"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_eager: bool = True
    policy_mode: str = "inline"
    policy_opa_url: str = "http://localhost:8181"
    policy_opa_path: str = "/v1/data/lattice_jit/policy"
    policy_opa_timeout_seconds: float = 2.0
    policy_opa_fail_closed: bool = False
    model_provider: str = "stub"
    litellm_model: str = "gpt-4o-mini"
    litellm_temperature: float = 0.0
    litellm_max_output_tokens: int | None = None
    litellm_deepseek_api_key: str = ""
    litellm_deepseek_base_url: str = "https://api.deepseek.com/v1"
    litellm_prompt_caching_enabled: bool = False
    load_shedding_enabled: bool = False
    load_shedding_max_items_per_minute: int = 100
    load_shedding_window_seconds: int = 60
    opa_health_check_interval_seconds: int = 30
    default_tenant_id: UUID = Field(default=UUID("00000000-0000-0000-0000-000000000001"))
    max_context_tokens: int = 12_000
    context_item_char_budget: int = 2_400
    cache_ttl_seconds: int = 3_600
    router_mode: str = "baseline"
    router_max_nodes: int = 8
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
