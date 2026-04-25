# Lattice-JIT Compiler v3.1 Initial Repo Plan

## Summary
- Build the project as a **Python-first modular monorepo**, not as day-one microservices. We will keep one FastAPI app, one Celery worker, and one Typer CLI, with future service boundaries expressed as Python packages.
- The first implementation slice is a **thin vertical path**: `Git/local files -> snapshot ingest -> lattice store -> context compile -> Phase A answer -> Phase B placeholder/polling -> provenance output`.
- The repo will be **local-first OSS** with `Docker Compose`, using **real Postgres and Redis** from day one. Model execution, semantic routing, and some governance behaviors will be behind adapters, with deterministic local stubs enabled by default.
- The first runnable surfaces are **HTTP API + CLI**. Reviewer web UI, SharePoint/Confluence/PDF connectors, and full calibration automation stay out of the first scaffold.

## Implementation Changes
- Use a single root Python workspace with `uv`, shared lint/type/test config, and one lockfile. Standard toolchain: `FastAPI`, `Typer`, `SQLAlchemy 2`, `Pydantic v2`, `Celery`, `Redis`, `pytest`, `ruff`, `mypy`.
- Create this top-level repo structure:

```text
apps/
  api/
  cli/
  worker/
packages/
  contracts/
  core/
  connectors/git_local/
  lattice/
  runtime/
  governance/
  policy/
  storage/
  model_proxy/
ops/
  opa/
  docker/
docs/
tests/
```

- `apps/api` owns HTTP entrypoints, request/response mapping, health endpoints, and answer polling.
- `apps/cli` owns operator commands mirroring the main API flows: ingest, query, answer-status, review-list.
- `apps/worker` owns Celery app setup plus async jobs for ingest continuation, Phase B verification, cache invalidation, and placeholder scheduled governance jobs.
- `packages/contracts` is the canonical public contract layer. It must define `KnowledgeNode`, `KnowledgeEdge`, `PolicyBundle`, `CompiledContextManifest`, `AnswerEnvelope`, `ReviewItem`, and all enums. Every contract includes `tenant_id`, even though local dev runs single-tenant.
- `packages/core` owns config loading, dependency wiring, logging, IDs, error model, and feature flags.
- `packages/connectors/git_local` is the only real connector in slice 1. It snapshots a local repo path and git ref, extracts files/sections, and creates source nodes.
- `packages/lattice` owns graph persistence rules, traversal, dirty propagation, cycle handling, node/edge ranking helpers, and provenance references.
- `packages/runtime` owns the query pipeline: semantic router adapter, subgraph selection, context compiler, token budgeting, Phase A orchestrator, and Phase B handoff.
- `packages/governance` owns typed-fact validation, review queue contracts, adaptive decay functions, audit event writing, and calibration/reviewer-load-shedding interfaces. Most advanced jobs are scaffolded now and fully implemented later.
- `packages/policy` owns policy evaluation behind an adapter. The contract is real now; dev defaults to a local inline evaluator, while `ops/opa` contains the OPA-compatible policy bundle and future sidecar wiring.
- `packages/storage` owns SQLAlchemy models/migrations/repositories plus Redis cache/broker access. It must define real persistence for `source_snapshots`, `knowledge_nodes`, `knowledge_edges`, `compiled_context_manifests`, `compiled_context_items`, `policy_bundles`, `answer_events`, `review_queue`, and `feedback_labels`.
- `packages/model_proxy` owns the model-provider abstraction. It must ship with a deterministic stub provider and a LiteLLM adapter behind the same interface.
- `docs/` should immediately contain the architecture overview, HTTP/CLI contracts, and a short ADR explaining why we chose a modular monorepo over separate services.

## Public Interfaces
- `POST /v1/snapshots/git`
  Request: `tenant_id`, `repo_path`, `git_ref|null`, `include_globs[]`, `exclude_globs[]`
  Response: `snapshot_id`, `root_node_id`, `status`
- `POST /v1/queries`
  Request: `tenant_id`, `query`, `snapshot_id|null`, `subgraph_ids[]|null`, `phase_b_mode` with `auto|off|force`
  Response: `answer_id`, `phase_a`, `phase_b_status`, `manifest_id`
- `GET /v1/answers/{answer_id}`
  Response: `phase`, `status`, `answer_text`, `confidence_band`, `provisional`, `provenance[]`, `conflict_flags[]`
- `GET /v1/review-queue`
  Response: list of review items for CLI/operator use. UI is deferred, but the contract is real now.
- CLI commands mirror those APIs: `ingest git`, `query`, `answer get`, `review list`
- Internal contract rule: store **both** `source_confidence` and `serving_confidence`; decay and calibration only update `serving_confidence`.

## Test Plan
- Unit tests for graph cycle resolution, dirty propagation, token-budget packing, policy bundle generation, adaptive decay, and confidence-band calculation.
- Repository tests for Postgres persistence of nodes, edges, manifests, answer events, and review items.
- Integration test for the first full slice: ingest a small local git repo, run a query, produce Phase A answer, persist provenance, then poll a stubbed Phase B result.
- Cache test proving repeated equivalent queries reuse the compiled context manifest from Redis instead of recompiling.
- API and CLI parity tests proving the same core services are exercised through both entrypoints.
- Local environment test proving `docker compose up` boots Postgres, Redis, API, and worker successfully with no external model dependency.

## Assumptions And Defaults
- Local development is single-tenant and authless, but all contracts and tables retain `tenant_id` so we do not paint ourselves into a corner.
- Only `Git/local files` are real ingestion sources in the first slice; `Confluence`, `SharePoint`, and `PDF` connectors remain future adapters, not scaffolded as active implementations.
- The semantic router starts as a deterministic adapter with a clean interface; the future `semantic-router` integration must plug into that interface without changing API contracts.
- The default model path is a deterministic stub provider; LiteLLM wiring exists but is optional in the first runnable scaffold.
- Governance is present as contracts and storage from the start, but reviewer web UI, full isotonic calibration jobs, full load shedding, and full OPA sidecar enforcement are deferred behind the chosen package boundaries.
- Implementation order should be: root workspace/tooling, shared contracts/core, storage/cache layer, API/CLI/worker entrypoints, git/local ingestion, runtime query path, governance/policy/model adapters, then tests and docs.
