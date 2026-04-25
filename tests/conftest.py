from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from lattice_jit.core import Settings, build_container
from lattice_jit.core.settings import get_settings


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite+pysqlite:///{db_path}"


@pytest.fixture(autouse=True)
def clear_cached_settings() -> Iterator[None]:
    get_settings.cache_clear()
    try:
        from lattice_jit.apps.api.main import get_container as api_get_container
        from lattice_jit.apps.cli.main import get_container as cli_get_container

        api_get_container.cache_clear()
        cli_get_container.cache_clear()
    except Exception:
        pass
    yield
    get_settings.cache_clear()


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=_sqlite_url(tmp_path / "lattice_jit.sqlite3"),
        redis_url="memory://",
        celery_broker_url="redis://localhost:6379/1",
        celery_result_backend="redis://localhost:6379/2",
        celery_eager=True,
        model_provider="stub",
    )


@pytest.fixture
def container(test_settings: Settings):
    return build_container(test_settings)


@pytest.fixture
def sample_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "sample_workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text(
        "# Sample Workspace\n\nThe auth service is owned by the platform team.\n",
        encoding="utf-8",
    )
    (workspace / "auth.py").write_text(
        "def check_auth(user):\n"
        "    return user.is_active\n"
        "\n"
        "# Policy: enforce auth before account reads.\n",
        encoding="utf-8",
    )
    (workspace / "policy.md").write_text(
        "Compliance policy: customer identifiers must remain redacted in provisional answers.\n",
        encoding="utf-8",
    )
    return workspace
