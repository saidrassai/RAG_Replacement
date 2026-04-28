from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from uuid import uuid4

import httpx
import pytest


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is not installed")
def test_docker_compose_config_is_valid() -> None:
    result = subprocess.run(
        ["docker", "compose", "-f", "ops/docker/docker-compose.yml", "config"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def _docker_daemon_available() -> bool:
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _find_free_host_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _running_services(compose: list[str], env: dict[str, str]) -> set[str]:
    result = subprocess.run(
        compose + ["ps", "--services", "--status", "running"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _postgres_count_for_tenant(compose: list[str], env: dict[str, str], table: str, tenant_id: str) -> int:
    query = f"SELECT COUNT(*) FROM {table} WHERE tenant_id = '{tenant_id}'::uuid;"
    result = subprocess.run(
        compose
        + ["exec", "-T", "postgres", "psql", "-U", "postgres", "-d", "lattice_jit", "-t", "-A", "-c", query],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return int(result.stdout.strip() or "0")


def _prepare_fixture_repo(compose: list[str], env: dict[str, str], repo_path: str) -> None:
    command = (
        "set -euo pipefail; "
        f"rm -rf {repo_path}; "
        f"mkdir -p {repo_path}; "
        f"printf 'def check_auth(user):\\n    return user.is_active\\n' > {repo_path}/auth.py; "
        f"printf '# Demo\\nPolicy and auth notes.\\n' > {repo_path}/README.md"
    )
    result = subprocess.run(
        compose + ["exec", "-T", "api", "sh", "-lc", command],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is not installed")
def test_docker_compose_boots_local_stack() -> None:
    if not _docker_daemon_available():
        pytest.skip("docker daemon is not available in this environment")

    compose = ["docker", "compose", "-f", "ops/docker/docker-compose.yml"]
    api_port = _find_free_host_port()
    env = {**os.environ, "LJIT_API_PORT": str(api_port)}

    subprocess.run(compose + ["down", "-v"], capture_output=True, text=True, check=False, env=env)
    try:
        up = subprocess.run(
            compose + ["up", "--build", "-d"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert up.returncode == 0, up.stderr

        expected_services = {"postgres", "redis", "api", "worker"}
        service_deadline = time.time() + 30
        while time.time() < service_deadline:
            if expected_services.issubset(_running_services(compose, env)):
                break
            time.sleep(2)
        else:
            running = _running_services(compose, env)
            pytest.fail(f"docker compose did not start expected services: {sorted(running)}")

        deadline = time.time() + 120
        last_error = ""
        while time.time() < deadline:
            try:
                response = httpx.get(f"http://127.0.0.1:{api_port}/healthz", timeout=2.0)
                if response.status_code == 200 and response.json() == {"status": "ok"}:
                    break
            except Exception as exc:  # pragma: no cover - exercised only with docker daemon access
                last_error = str(exc)
            time.sleep(2)
        else:
            pytest.fail(f"api health check did not become ready: {last_error}")

        tenant_id = str(uuid4())
        fixture_repo_path = "/tmp/ljit-e2e-fixture"
        _prepare_fixture_repo(compose, env, fixture_repo_path)

        snapshot_response = httpx.post(
            f"http://127.0.0.1:{api_port}/v1/snapshots/git",
            json={
                "tenant_id": tenant_id,
                "repo_path": fixture_repo_path,
                "include_globs": ["*.py", "*.md"],
                "exclude_globs": [],
            },
            timeout=60.0,
        )
        assert snapshot_response.status_code == 200, snapshot_response.text
        snapshot_id = snapshot_response.json()["snapshot_id"]

        query_response = httpx.post(
            f"http://127.0.0.1:{api_port}/v1/queries",
            json={
                "tenant_id": tenant_id,
                "query": "Where is auth enforced?",
                "snapshot_id": snapshot_id,
                "phase_b_mode": "off",
            },
            timeout=30.0,
        )
        assert query_response.status_code == 200, query_response.text
        query_payload = query_response.json()

        compliance_query_response = httpx.post(
            f"http://127.0.0.1:{api_port}/v1/queries",
            json={
                "tenant_id": tenant_id,
                "query": "What does our compliance policy require?",
                "snapshot_id": snapshot_id,
                "phase_b_mode": "auto",
            },
            timeout=30.0,
        )
        assert compliance_query_response.status_code == 200, compliance_query_response.text

        answer_response = httpx.get(
            f"http://127.0.0.1:{api_port}/v1/answers/{query_payload['answer_id']}",
            params={"tenant_id": tenant_id},
            timeout=20.0,
        )
        assert answer_response.status_code == 200, answer_response.text

        review_queue_response = httpx.get(
            f"http://127.0.0.1:{api_port}/v1/review-queue",
            params={"tenant_id": tenant_id},
            timeout=20.0,
        )
        assert review_queue_response.status_code == 200, review_queue_response.text

        answer_payload = answer_response.json()
        review_payload = review_queue_response.json()
        assert answer_payload["answer_id"] == query_payload["answer_id"]
        assert "manifest_id" in query_payload
        assert isinstance(review_payload["items"], list)
        assert len(review_payload["items"]) >= 1

        assert _postgres_count_for_tenant(compose, env, "knowledge_nodes", tenant_id) > 0
        assert _postgres_count_for_tenant(compose, env, "knowledge_edges", tenant_id) > 0
        assert _postgres_count_for_tenant(compose, env, "compiled_context_manifests", tenant_id) > 0
        assert _postgres_count_for_tenant(compose, env, "answer_events", tenant_id) > 0
        assert _postgres_count_for_tenant(compose, env, "review_queue", tenant_id) > 0
    finally:
        subprocess.run(compose + ["down", "-v"], capture_output=True, text=True, check=False, env=env)
