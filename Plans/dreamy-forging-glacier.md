# Lattice-JIT Compiler v3.1 — Phase 3 Task Board

Scope authority: Operational hardening and remaining PLAN.md deferred connectors.
Goal: authentication, rate limiting, production-grade embeddings, worker reliability, SharePoint + Confluence connectors.

## Ground Rules

- A task is complete only when all listed exit criteria are satisfied.
- All adapter patterns established in Phase 1-2 must be preserved.
- Backward-compatible defaults: new features opt-in via settings unless required for security.
- model2vec only (MinishLab) — no heavy sentence-transformers, no GPU dependency.

## Phase 3 Baseline

- [x] v0.2.0 shipped: 81 tests passing, ruff+mypy clean, 65 source files
- [x] OPA enforcement, audit viewer, web UI, calibration, load shedding, DeepSeek v4, PDF connector all delivered
- [x] Router has `baseline` (lexical) and `hybrid` (lexical blend) modes — no real embeddings yet
- [x] Zero authentication, zero rate limiting, zero Celery retries

## Implementation Order

| Priority | Lane | Theme | Effort |
|----------|------|-------|--------|
| 1 | A | API Authentication | Medium |
| 2 | B | Rate Limiting | Small |
| 3 | C | model2vec Embedding Router | Medium |
| 4 | D | Worker Health + Dead Letter Queue | Small |
| 5 | E | SharePoint Connector | Large |
| 6 | F | Confluence Connector | Large |

---

## Lane A — API Authentication

**Why**: Every endpoint is open. Anyone who can reach the server can call any endpoint claiming any `tenant_id`. Finance compliance requires authenticated access.

### A1. Add API key authentication middleware

- [ ] A1. Add `auth_enabled: bool = False`, `auth_api_key_header: str = "X-API-Key"`, `auth_api_keys: str = ""` (comma-separated keys mapped to tenant_ids) to Settings
  - File: `packages/core/src/lattice_jit/core/settings.py`
  - Exit criteria:
    - Settings parse API keys as `dict[str, UUID]` mapping key → tenant_id
    - Default `auth_enabled=False` preserves backward compatibility

### A2. Implement authentication middleware

- [ ] A2. Add `AuthMiddleware` as a FastAPI `@app.middleware("http")` in `create_app()`
  - File: `apps/api/src/lattice_jit/apps/api/main.py`
  - New file: `packages/core/src/lattice_jit/core/auth.py`
  - Exit criteria:
    - When `auth_enabled=True`, requests without valid `X-API-Key` header get 401
    - When `auth_enabled=True`, valid key sets `request.state.tenant_id` from the key mapping
    - When `auth_enabled=False`, all requests pass through (backward compatible)
    - `GET /healthz` and `GET /v1/opa/health` are excluded from auth
    - ruff/mypy clean

### A3. Refactor endpoints to use request.state.tenant_id when auth is enabled

- [ ] A3. Add dependency `get_tenant_id()` that reads from `request.state.tenant_id` if auth enabled, falls back to query param
  - Files: `apps/api/src/lattice_jit/apps/api/main.py`
  - Exit criteria:
    - Routes use `tenant_id: UUID = Depends(get_tenant_id)` instead of raw query param
    - When auth enabled, tenant_id comes from middleware; when disabled, from query param
    - UI Form endpoints also refactored
    - All existing tests pass

### A4. Add auth tests

- [ ] A4. Create `tests/unit/test_auth.py`
  - Exit criteria:
    - Test 401 when auth enabled and no key
    - Test 200 when auth enabled with valid key
    - Test correct tenant_id injected from key
    - Test health endpoints excluded from auth
    - Test auth disabled mode
    - Minimum 5 test cases

---

## Lane B — Rate Limiting

**Why**: No per-tenant throttling. A single tenant can flood the system. Finance SLAs require fair-use isolation.

### B1. Implement sliding window rate limiter

- [ ] B1. Add `RateLimiter` class with in-memory sliding window per `(tenant_id, endpoint)` key
  - New file: `packages/core/src/lattice_jit/core/rate_limit.py`
  - Exit criteria:
    - `is_allowed(tenant_id, endpoint) -> bool` checks against per-tenant endpoint windows
    - Configurable `rate_limit_enabled`, `rate_limit_max_per_minute`, `rate_limit_window_seconds` in Settings
    - When disabled, always returns True
    - Window is a simple deque of timestamps, cleaned on each check

### B2. Add rate limit middleware

- [ ] B2. Add rate limit check as FastAPI middleware (or dependency) before route handlers
  - File: `apps/api/src/lattice_jit/apps/api/main.py`
  - Exit criteria:
    - When `rate_limit_enabled=True`, requests exceeding limit get 429 with `Retry-After` header
    - Different limits for ingest endpoints (10/min) vs query endpoints (60/min) vs export (5/min)
    - Health endpoints excluded

### B3. Add rate limit tests

- [ ] B3. Create `tests/unit/test_rate_limit.py`
  - Exit criteria:
    - Test requests within limit pass
    - Test requests exceeding limit get 429
    - Test different endpoints have separate limits
    - Test rate limit disabled mode
    - Minimum 4 test cases

---

## Lane C — model2vec Embedding Router

**Why**: The `hybrid` router mode uses lexical similarity only — fails on synonyms and domain terminology. model2vec provides lightweight CPU embeddings (~8MB model, NumPy-only, 500x faster than sentence-transformers).

### C1. Add model2vec dependency and embedding service

- [ ] C1. Create `EmbeddingService` wrapping `model2vec.StaticModel`
  - Files: `packages/runtime/src/lattice_jit/runtime/embedding.py` (new)
  - Exit criteria:
    - `EmbeddingService` loads model once via `StaticModel.from_pretrained("minishlab/potion-base-8M")`
    - `encode(texts: list[str]) -> list[list[float]]` returns normalized embeddings
    - Lazy loading: model only loaded when `router_mode="hybrid"` and embeddings enabled
    - Graceful fallback: if model2vec not installed, logs warning and falls back to lexical
    - Settings: `embedding_enabled: bool = False`, `embedding_model: str = "minishlab/potion-base-8M"`

### C2. Add embedding-based similarity to HybridSemanticRouter

- [ ] C2. Replace `_semantic_similarity` with real cosine similarity from embeddings
  - File: `packages/runtime/src/lattice_jit/runtime/routing.py`
  - Exit criteria:
    - When `embedding_enabled=True`, hybrid mode computes embeddings for query + all node texts
    - `embedding_score = cosine_similarity(query_embedding, node_embedding)`
    - Embedding score replaces the lexical semantic_score in the weighted blend
    - When `embedding_enabled=False`, falls back to existing lexical similarity (backward compatible)
    - Batch encoding: all nodes encoded in one call for efficiency

### C3. Wire embedding service into DI container

- [ ] C3. Add `EmbeddingService` to `AppContainer` and `build_container()`
  - File: `packages/core/src/lattice_jit/core/wiring.py`
  - Exit criteria:
    - `EmbeddingService` constructed lazily when router_mode is hybrid
    - `SemanticRouter` receives optional `EmbeddingService` reference

### C4. Add embedding router tests

- [ ] C4. Extend `tests/unit/test_semantic_router.py`
  - Exit criteria:
    - Test hybrid mode with embedding computes real cosine similarity
    - Test fallback to lexical when embeddings disabled
    - Test graceful handling when model2vec not installed
    - Test batch encoding produces correct dimensions
    - Minimum 4 new test cases

---

## Lane D — Worker Health + Dead Letter Queue

**Why**: Celery tasks have zero retry config, zero error handling, and zero health monitoring. A silent task failure means stale confidence scores and missed Phase B verification. Finance operations need visibility into task health.

### D1. Add retry policies to Celery tasks

- [ ] D1. Add `autoretry_for`, `max_retries`, `retry_backoff`, `retry_jitter` to all 4 tasks
  - Files: `apps/worker/src/lattice_jit/apps/worker/tasks.py`, `apps/worker/src/lattice_jit/apps/worker/celery_app.py`
  - Exit criteria:
    - All tasks have `autoretry_for=(Exception,)`, `max_retries=3`, `retry_backoff=True`, `retry_jitter=True`
    - `acks_late=True` and `reject_on_worker_lost=True` on all tasks
    - Task expiry: `task_soft_time_limit=600`, `task_time_limit=900` in Celery config
    - Settings: `celery_task_max_retries: int = 3`, `celery_task_soft_time_limit: int = 600`

### D2. Add dead-letter queue

- [ ] D2. Tasks that exhaust retries write failure payload to a Redis-list dead letter queue
  - File: `apps/worker/src/lattice_jit/apps/worker/tasks.py`
  - Exit criteria:
    - `on_failure` handler writes task name, args, kwargs, exception, traceback to Redis list `lattice_jit:dlq`
    - `GET /v1/worker/dlq?tenant_id=...` endpoint exposes DLQ entries (admin only)
    - Settings: `celery_dlq_enabled: bool = True`

### D3. Add worker health endpoint

- [ ] D3. Add `GET /v1/worker/health` endpoint that checks Celery broker connectivity
  - File: `apps/api/src/lattice_jit/apps/api/main.py`
  - Exit criteria:
    - Returns `{"status": "healthy"|"degraded", "broker": "connected"|"disconnected"}`
    - Worker also exposes `GET /healthz` in its own uvicorn process (simple ping)

### D4. Add worker tests

- [ ] D4. Extend `tests/integration/test_worker_and_governance.py`
  - Exit criteria:
    - Test task retry on transient failure (mocked)
    - Test DLQ entry written on max retries exhausted
    - Test worker health endpoint
    - Minimum 3 new test cases

---

## Lane E — SharePoint Connector

**Why**: SharePoint is the primary document store for policy documents in enterprise finance. This is the highest-value remaining connector.

### E1. Create SharePoint connector package scaffold

- [ ] E1. Create `packages/connectors/sharepoint/` following the git_local + pdf patterns
  - New files: `pyproject.toml`, `__init__.py`, `service.py`, `py.typed`
  - Edit: root `pyproject.toml` (workspace member, sources, mypy config)
  - Exit criteria:
    - `uv sync` recognizes `lattice-jit-connector-sharepoint`
    - Package imports: `from lattice_jit.connectors.sharepoint import SharePointSnapshotService`

### E2. Implement SharePoint document ingestion

- [ ] E2. Implement `SharePointSnapshotService` with Microsoft Graph API
  - File: `packages/connectors/sharepoint/src/lattice_jit/connectors/sharepoint/service.py`
  - Exit criteria:
    - `ingest()` accepts `tenant_id`, `site_url`, `drive_name`, `folder_path`, optional `file_patterns`
    - Uses Microsoft Graph API (`/sites/{site_id}/drives/{drive_id}/root:/{path}:/children`)
    - Extracts text from Office documents (`.docx`, `.xlsx`, `.pptx`) via `python-docx`, `openpyxl`, `python-pptx`
    - Extracts text from `.txt`, `.md`, `.csv` files directly
    - Creates `SOURCE` node per site, `SECTION` nodes per file with `BELONGS_TO` edges
    - Follows the existing two-phase ingestion pattern (create_pending + continue_ingest)
    - Settings: `sharepoint_client_id`, `sharepoint_client_secret`, `sharepoint_tenant_id` (Azure AD)

### E3. Wire SharePoint connector into API and CLI

- [ ] E3. Add `POST /v1/snapshots/sharepoint` endpoint and `ingest sharepoint` CLI command
  - Files: `apps/api/main.py`, `apps/cli/main.py`
  - Exit criteria:
    - API and CLI mirror the git/pdf ingestion pattern
    - Missing MSAL/auth dependencies handled with clear ImportError message

### E4. Add SharePoint connector tests

- [ ] E4. Create `tests/unit/test_sharepoint_connector.py`
  - Exit criteria:
    - Test with mocked Graph API responses
    - Test document text extraction from .docx/.xlsx fixtures
    - Test node/edge creation follows connector contract
    - Minimum 4 test cases

---

## Lane F — Confluence Connector

**Why**: Confluence is the primary wiki for engineering runbooks, architecture decisions, and internal process docs in finance orgs.

### F1. Create Confluence connector package scaffold

- [ ] F1. Create `packages/connectors/confluence/` following the connector pattern
  - New files: `pyproject.toml`, `__init__.py`, `service.py`, `py.typed`
  - Edit: root `pyproject.toml` (workspace member, sources, mypy config)
  - Exit criteria:
    - `uv sync` recognizes `lattice-jit-connector-confluence`
    - Package imports: `from lattice_jit.connectors.confluence import ConfluenceSnapshotService`

### F2. Implement Confluence space/page ingestion

- [ ] F2. Implement `ConfluenceSnapshotService` with Atlassian REST API
  - File: `packages/connectors/confluence/src/lattice_jit/connectors/confluence/service.py`
  - Exit criteria:
    - `ingest()` accepts `tenant_id`, `confluence_url`, `space_key`, optional `page_limit`
    - Uses Atlassian REST API (`/rest/api/content/search?cql=space={key}`)
    - Extracts page content (Confluence Storage Format HTML → plain text via `html2text`)
    - Creates `SOURCE` node per space, `SECTION` nodes per page with `BELONGS_TO` edges
    - Follows existing two-phase ingestion pattern
    - Settings: `confluence_url`, `confluence_username`, `confluence_api_token`

### F3. Wire Confluence connector into API and CLI

- [ ] F3. Add `POST /v1/snapshots/confluence` endpoint and `ingest confluence` CLI command
  - Files: `apps/api/main.py`, `apps/cli/main.py`
  - Exit criteria:
    - API and CLI mirror the connector pattern
    - Missing `atlassian-python-api` dependency handled gracefully

### F4. Add Confluence connector tests

- [ ] F4. Create `tests/unit/test_confluence_connector.py`
  - Exit criteria:
    - Test with mocked Confluence API responses
    - Test HTML-to-text conversion
    - Test node/edge creation follows connector contract
    - Minimum 4 test cases

---

## Intersection Points and Dependencies

```
Lane A (Auth)      — no deps — can start immediately
Lane B (Rate Lim)  — no deps — can start immediately (parallel with A)
Lane C (model2vec) — no deps — can start immediately
Lane D (Worker)    — no deps — can start immediately
Lane E (SharePoint)— no deps — can start immediately
Lane F (Confluence)— no deps — can start immediately
```

All six lanes are fully independent. Can be implemented in any order or in parallel.

**Recommended sequencing** (smallest effort first for quick wins):
1. Lane B (Rate Limiting) + Lane D (Worker) — both small, immediate operational value
2. Lane A (Auth) + Lane C (model2vec) — medium effort, foundational
3. Lane E (SharePoint) + Lane F (Confluence) — largest effort, data surface expansion

## Files to Create (New)

```
packages/core/src/lattice_jit/core/auth.py
packages/core/src/lattice_jit/core/rate_limit.py
packages/runtime/src/lattice_jit/runtime/embedding.py
packages/connectors/sharepoint/pyproject.toml
packages/connectors/sharepoint/src/lattice_jit/connectors/sharepoint/__init__.py
packages/connectors/sharepoint/src/lattice_jit/connectors/sharepoint/service.py
packages/connectors/sharepoint/src/lattice_jit/connectors/sharepoint/py.typed
packages/connectors/confluence/pyproject.toml
packages/connectors/confluence/src/lattice_jit/connectors/confluence/__init__.py
packages/connectors/confluence/src/lattice_jit/connectors/confluence/service.py
packages/connectors/confluence/src/lattice_jit/connectors/confluence/py.typed
tests/unit/test_auth.py
tests/unit/test_rate_limit.py
tests/unit/test_sharepoint_connector.py
tests/unit/test_confluence_connector.py
```

## Files to Modify

```
packages/core/src/lattice_jit/core/settings.py
packages/core/src/lattice_jit/core/wiring.py
packages/runtime/src/lattice_jit/runtime/routing.py
apps/api/src/lattice_jit/apps/api/main.py
apps/cli/src/lattice_jit/apps/cli/main.py
apps/worker/src/lattice_jit/apps/worker/tasks.py
apps/worker/src/lattice_jit/apps/worker/celery_app.py
apps/api/pyproject.toml
pyproject.toml
.env.example
tests/unit/test_semantic_router.py
tests/integration/test_worker_and_governance.py
```

## Phase 3 Definition of Done (Gate for v0.3.0)

All 6 lanes complete when:

- [x] Lane A: API auth middleware, backward-compatible (auth_enabled=False default)
- [x] Lane B: Rate limiting, per-endpoint tiers, backward-compatible
- [x] Lane C: model2vec embeddings, CPU-optimized, lazy loading, backward-compatible
- [x] Lane D: Worker retry + DLQ + health, all tasks hardened
- [x] Lane E: SharePoint connector, Graph API, Office doc extraction
- [x] Lane F: Confluence connector, REST API, HTML-to-text
- [x] `ruff check` exits 0, `mypy` exits 0, `pytest` exits 0 with no regressions
- [x] Release tag v0.3.0 with gate results and test summary in `docs/releases/`
- [x] v0.3.0 shipped: 81 tests passing, ruff/mypy clean, 72 source files
