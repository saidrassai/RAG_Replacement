#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-full}"
if [[ "$MODE" != "full" && "$MODE" != "--readme-only" ]]; then
  echo "Usage: bash ops/scripts/verify_readme_quickstart.sh [--readme-only]" >&2
  exit 2
fi

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

verify_readme_commands() {
  local readme="README.md"

  grep -Fq '`uv sync --all-packages`' "$readme" || {
    echo "README quick start is missing: uv sync --all-packages" >&2
    exit 1
  }

  grep -Fq '`docker compose -f ops/docker/docker-compose.yml up --build`' "$readme" || {
    echo "README quick start is missing: docker compose up --build command" >&2
    exit 1
  }

  grep -Fq '`uv run --all-packages pytest`' "$readme" || {
    echo "README quick start is missing: uv run --all-packages pytest" >&2
    exit 1
  }
}

find_free_port() {
  python - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind(("127.0.0.1", 0))
    print(s.getsockname()[1])
PY
}

wait_for_services() {
  local compose_file="$1"
  local deadline=$((SECONDS + 30))
  local expected=(postgres redis api worker)

  while (( SECONDS < deadline )); do
    mapfile -t running < <(docker compose -f "$compose_file" ps --services --status running)
    local missing=0
    for service in "${expected[@]}"; do
      if ! printf '%s\n' "${running[@]}" | grep -Fxq "$service"; then
        missing=1
        break
      fi
    done
    if [[ "$missing" -eq 0 ]]; then
      return 0
    fi
    sleep 2
  done

  echo "Compose services did not all reach running state" >&2
  docker compose -f "$compose_file" ps >&2 || true
  return 1
}

wait_for_healthz() {
  local url="$1"
  local deadline=$((SECONDS + 120))

  while (( SECONDS < deadline )); do
    if curl -fsS "$url" | grep -Fq '{"status":"ok"}'; then
      return 0
    fi
    sleep 2
  done

  echo "API health check did not become ready: $url" >&2
  return 1
}

verify_readme_commands

if [[ "$MODE" == "--readme-only" ]]; then
  echo "README quick-start command mapping is valid."
  exit 0
fi

require_command uv
require_command docker
require_command curl
require_command python

COMPOSE_FILE="ops/docker/docker-compose.yml"
API_PORT="$(find_free_port)"
export LJIT_API_PORT="$API_PORT"

created_env=0
if [[ ! -f .env ]]; then
  cp .env.example .env
  created_env=1
fi

cleanup() {
  docker compose -f "$COMPOSE_FILE" down -v >/dev/null 2>&1 || true
  if [[ "$created_env" -eq 1 ]]; then
    rm -f .env
  fi
}
trap cleanup EXIT

echo "[1/4] Syncing dependencies"
uv sync --all-packages

echo "[2/4] Starting local stack"
docker compose -f "$COMPOSE_FILE" up --build -d
wait_for_services "$COMPOSE_FILE"
wait_for_healthz "http://127.0.0.1:${API_PORT}/healthz"

echo "[3/4] Running tests"
uv run --all-packages pytest

echo "[4/4] Quick-start verification completed successfully"
