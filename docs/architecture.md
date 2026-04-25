# Architecture Overview

`Lattice-JIT Compiler v3.1` is implemented as a Python-first modular monorepo with one FastAPI app, one Typer CLI, and one Celery worker over shared packages.

## First vertical slice

1. `POST /v1/snapshots/git` ingests a local repo path or git ref and persists a source snapshot plus lattice nodes and edges.
2. `POST /v1/queries` evaluates policy, compiles a context manifest, produces a deterministic Phase A answer, and optionally hands Phase B to Celery.
3. `GET /v1/answers/{answer_id}` returns the latest answer event, including a verified Phase B placeholder if it has completed.
4. `GET /v1/review-queue` exposes governance queue items for operator tooling.

## Package roles

- `packages/contracts`: shared Pydantic contracts and enums.
- `packages/core`: settings, logging, IDs, and dependency wiring.
- `packages/storage`: SQLAlchemy tables, repositories, and Redis-compatible cache abstraction.
- `packages/connectors/git_local`: real ingestion connector for local files and git refs.
- `packages/lattice`: cycle handling, dirty propagation, ranking, and confidence helpers.
- `packages/runtime`: semantic routing, context compilation, Phase A orchestration, Phase B scheduling.
- `packages/policy`: inline policy evaluator with an OPA-compatible contract.
- `packages/governance`: adaptive decay, typed fact registry, review queue coordination.
- `packages/model_proxy`: deterministic stub provider and LiteLLM adapter.

## Local-first defaults

- Postgres and Redis are the default runtime dependencies.
- The default model provider is the deterministic stub provider.
- Celery runs eagerly in plain local development and asynchronously in Docker Compose.
