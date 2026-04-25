from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from lattice_jit.apps.api.main import create_app
from lattice_jit.apps.api.main import get_container as api_get_container
from lattice_jit.apps.cli.main import app as cli_app
from lattice_jit.apps.cli.main import get_container as cli_get_container
from lattice_jit.core import build_container
from typer.testing import CliRunner


def test_api_and_cli_share_same_services(test_settings, sample_workspace: Path) -> None:
    api_get_container.cache_clear()
    cli_get_container.cache_clear()

    test_container = build_container(test_settings)
    app = create_app()
    app.dependency_overrides[api_get_container] = lambda: test_container
    client = TestClient(app)
    runner = CliRunner()
    tenant_id = uuid4()

    snapshot_response = client.post(
        "/v1/snapshots/git",
        json={
            "tenant_id": str(tenant_id),
            "repo_path": str(sample_workspace),
            "include_globs": ["*.py", "*.md"],
            "exclude_globs": [],
        },
    )
    snapshot_id = snapshot_response.json()["snapshot_id"]

    cli_result = runner.invoke(
        cli_app,
        [
            "query",
            "--tenant-id",
            str(tenant_id),
            "--query",
            "Which file mentions auth?",
            "--snapshot-id",
            snapshot_id,
            "--phase-b-mode",
            "off",
        ],
        env={
            "LJIT_DATABASE_URL": test_settings.database_url,
            "LJIT_REDIS_URL": test_settings.redis_url,
            "LJIT_CELERY_EAGER": "true",
        },
    )
    api_result = client.post(
        "/v1/queries",
        json={
            "tenant_id": str(tenant_id),
            "query": "Which file mentions auth?",
            "snapshot_id": snapshot_id,
            "phase_b_mode": "off",
        },
    )

    assert cli_result.exit_code == 0
    assert api_result.status_code == 200
    assert "phase_a" in cli_result.stdout
    assert api_result.json()["phase_a"]["answer_text"].startswith("Phase A provisional answer")
