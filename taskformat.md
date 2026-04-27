# Lattice-JIT Compiler v3.1 — Trimmed Task Board (v3)

Scope authority: PLAN.md and README.md only.
Goal: finish and ship the planned first scaffold with clear checkpoints and no scope creep.

## 1) Ground Rules

- A task is complete only when all listed exit criteria are satisfied.
- Do not add new components outside PLAN.md.
- Deferred items from PLAN.md remain deferred unless explicitly approved.
- For finance/fintech/healthcare use, apply the release checkpoints in Section 6 before production go-live.

## 2) Current Baseline (From Plan)

- [x] Monorepo shape exists: apps/, packages/, ops/, docs/, tests/
- [x] First vertical path implemented: ingest -> lattice store -> context compile -> Phase A -> Phase B placeholder/polling -> provenance
- [x] API + CLI + worker + storage + contracts + adapters exist
- [x] Docker assets and OPA scaffold exist
- [x] Docs exist: architecture, interfaces, ADR

## 3) Remaining Tasks To Close First Scaffold

### Lane A — Quality and Local Runtime Closure

- [x] A1. Make lint/type/test fully green in standard local run
  - Exit criteria:
    - ruff check exits 0
    - mypy exits 0
    - pytest exits 0

- [x] A2. Confirm docker compose local stack boot (Postgres, Redis, API, worker)
  - Exit criteria:
    - docker compose up --build starts all 4 services
    - API health endpoint responds successfully
  - Status:
    - Covered by `tests/e2e/test_docker_compose.py`
    - Verified in a docker-daemon-capable run: `pytest -q tests/e2e/test_docker_compose.py` -> `2 passed`

- [x] A3. Ensure e2e compose boot test runs in at least one docker-accessible environment
  - Exit criteria:
    - tests/e2e/test_docker_compose.py executes without skip in docker-capable environment
  - Status:
    - Verified non-skipped pass in docker-capable environment: `2 passed in 121.46s`

### Lane B — Contract and Interface Freeze

- [x] B1. Verify HTTP interfaces exactly match PLAN.md
  - Endpoints:
    - POST /v1/snapshots/git
    - POST /v1/queries
    - GET /v1/answers/{answer_id}
    - GET /v1/review-queue
  - Exit criteria:
    - Request/response fields match contracts and PLAN definitions

- [x] B2. Verify CLI mirrors API flows exactly
  - Commands:
    - ingest git
    - query
    - answer get
    - review list
  - Exit criteria:
    - Same core services exercised from both API and CLI paths

### Lane C — Test Plan Completion (As Written)

- [x] C1. Unit coverage check against PLAN list
  - Required areas:
    - cycle resolution
    - dirty propagation
    - token-budget packing
    - policy bundle generation
    - adaptive decay
    - confidence-band calculation
  - Exit criteria:
    - Tests present and passing for all listed areas

- [x] C2. Repository tests for persistence
  - Required tables/areas:
    - nodes, edges, manifests, answer events, review items
  - Exit criteria:
    - Persistence tests passing against Postgres

- [x] C3. Integration first-slice flow
  - Required path:
    - ingest local git repo -> query -> Phase A answer -> provenance persisted -> poll stubbed Phase B
  - Exit criteria:
    - Single integration test proving full path passes

- [x] C4. Cache reuse test
  - Required behavior:
    - equivalent repeated queries reuse compiled context manifest from Redis
  - Exit criteria:
    - Test proves reuse (no recompile on equivalent query)

- [x] C5. API/CLI parity test
  - Required behavior:
    - same core services used by both entrypoints
  - Exit criteria:
    - Parity test passes

### Lane D — Docs and Release Readiness for First Scaffold

- [x] D1. README quick start validation
  - Exit criteria:
    - Steps in README run as documented without hidden steps

- [x] D2. Architecture and interface docs consistency pass
  - Exit criteria:
    - docs/architecture.md and docs/interfaces.md reflect current behavior

- [x] D3. Release tag for first scaffold
  - Exit criteria:
    - v0.1.0 (or agreed equivalent) tagged on main
    - Release notes include gate results and test summary
  - Status:
    - Release notes created at `docs/releases/v0.1.0-slice1.md`
    - Quality gates verified in docker-capable environment: `26 passed`
    - Tag pushed: `v0.1.0` on `origin/main`

## 4) Explicitly Deferred (Do Not Treat As Incomplete First-Scaffold Work)

These are deferred by PLAN.md and must remain out of first-slice closure unless scope is formally changed:

- Reviewer web UI
- Full isotonic calibration automation
- Full load shedding automation
- Full OPA sidecar enforcement
- Additional connectors beyond Git/local files (Confluence, SharePoint, PDF)

## 5) If You Choose To Continue Beyond First Scaffold (Plan-Consistent Order)

Only start after Section 3 is complete.

- [ ] P1. Keep semantic router behind adapter; integrate stronger router without API contract changes
- [ ] P2. Keep default model stub path stable; evolve LiteLLM path behind same interface
- [ ] P3. Expand governance jobs from scaffold toward full implementations
- [ ] P4. Expand policy from inline default toward sidecar path when scope is approved

## 6) Regulated-Domain Go/No-Go Checklist (Finance / Fintech / Healthcare)

This is a release checkpoint, not new build scope.

- [ ] R1. Confirm tenant_id is present across all contracts/tables (already required by plan)
- [ ] R2. Confirm answer provenance is persisted and returned for all served answers
- [ ] R3. Confirm policy evaluation path is active for the chosen deployment mode (inline now; sidecar if approved)
- [ ] R4. Confirm audit/review queue flows are operational for human oversight
- [ ] R5. Confirm no undocumented behavior diverges from contracts in docs/interfaces

Go-live rule for regulated use: all R1–R5 must be checked.

## 7) Definition of Done

Project is complete for planned first scaffold when all are true:

- [x] Section 3 (A-D) fully complete
- [x] No failing quality gates
- [x] Test plan items in PLAN.md all passing
- [x] First scaffold release tag created

Project is complete beyond scaffold only if deferred scope is explicitly approved and then delivered.
