# Lattice-JIT Compiler v3.1

Python-first modular monorepo scaffold for the first vertical slice of the Lattice-JIT architecture.

## Workspace

- `apps/api`: FastAPI surface
- `apps/cli`: Typer operator CLI
- `apps/worker`: Celery worker and scheduled jobs
- `packages/*`: shared contracts and domain packages
- `ops/docker`: local-first Docker assets
- `ops/opa`: policy bundle scaffold

## Quick start

1. Install dependencies:
   - `uv sync --all-packages`
2. Copy `.env.example` to `.env` if you want local overrides.
3. Start the local stack:
   - `docker compose -f ops/docker/docker-compose.yml up --build`
4. Run tests:
   - `uv run --all-packages pytest`

## Quick start verification

Run the automated verifier to confirm README quick-start steps stay executable and in sync:

- `bash ops/scripts/verify_readme_quickstart.sh`

To validate README command mapping only (no docker/test execution):

- `bash ops/scripts/verify_readme_quickstart.sh --readme-only`
