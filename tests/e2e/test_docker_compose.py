from __future__ import annotations

import os
import socket
import shutil
import subprocess
import time

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
    finally:
        subprocess.run(compose + ["down", "-v"], capture_output=True, text=True, check=False, env=env)
