# Lattice-JIT Compiler v3.1 — Phase 2 Task Board

Scope authority: PLAN.md Section 4 (explicitly deferred items) + acknowledged operational gaps.
Goal: promote deferred scope to full implementation with finance-first prioritization, following the same discipline as Phase 1.

## Ground Rules

- A task is complete only when all listed exit criteria are satisfied.
- Do not add new components outside PLAN.md.
- All adapter patterns established in Phase 1 must be preserved.
- Finance-first: every lane must pass the regulated-domain checklist (Section 6 of taskformat.md) before closure.
- Default behavior must remain backward-compatible; production hardening is opt-in via settings.

## Phase 2 Baseline

- [x] v0.1.0 scaffold shipped: 36 tests passing, ruff+mypy clean
- [x] Regulated-domain checklist (R1-R5) complete
- [x] Adapter patterns: ModelProvider, PolicyEvaluatorProtocol, CacheStore, RouterBackend, PhaseBScheduler
- [x] Factory/build patterns: build_model_provider(), build_policy_evaluator(), build_cache_store()
- [x] DI container: AppContainer with build_container()
- [x] 10 ORM tables, 6 HTTP endpoints, 6 CLI commands

## Implementation Order (Finance-First Priority)

| Priority | Lane | Theme | Target Phase |
|----------|------|-------|-------------|
| 1 | F | Full OPA Sidecar Enforcement | 2a |
| 2 | G | Audit Trail Viewer | 2a |
| 3 | H | Reviewer Web UI | 2b |
| 4 | K | Real LLM Integration (DeepSeek v4) | 2b |
| 5 | I | Full Isotonic Calibration | 2c |
| 6 | J | Full Load Shedding | 2c |
| 7 | L | PDF Connector | 2c |

---

## Lane F — Full OPA Sidecar Enforcement

**Why**: Regulated environments cannot tolerate silent policy bypass. The current OPA sidecar falls back silently to inline on any HTTP error, missing key Rego rules, and has no health-check gating. Finance needs fail-closed capability and complete Rego coverage.

### F1. Extend Rego rules to cover full PolicyBundle contract

- [ ] F1. Add `human_gate_required` and `redaction_rules` rules to `ops/opa/policy.rego`
  - Exit criteria:
    - `opa eval` with `compliance` input returns `human_gate_required=true`, `redaction_rules=["mask_identifiers"]`
    - `opa eval` with `general` input returns `human_gate_required=false`, `redaction_rules=[]`
    - Existing policy tests still pass

### F2. Add OPA service to docker-compose

- [ ] F2. Add `opa` service to `ops/docker/docker-compose.yml` using `openpolicyagent/opa:latest`
  - Exit criteria:
    - `docker compose up --build` starts OPA alongside postgres, redis, api, worker
    - API and worker env blocks include `LJIT_POLICY_MODE=opa_http`, `LJIT_POLICY_OPA_URL=http://opa:8181`
    - OPA health endpoint responds successfully

### F3. Add fail-closed mode to OPA HTTP evaluator

- [ ] F3. Add `policy_opa_fail_closed: bool = False` to Settings and `OpaHttpPolicyEvaluator`
  - Exit criteria:
    - `fail_closed=True` with unreachable OPA raises `LatticeJitError` for compliance/security queries
    - `fail_closed=False` with unreachable OPA falls back to inline (backward-compatible)
    - General queries (non-regulated) always fall back regardless of fail_closed
    - Settings, wiring, and config all typed; ruff/mypy clean

### F4. Add OPA health-check endpoint

- [ ] F4. Add `GET /v1/opa/health` endpoint to API
  - Exit criteria:
    - Returns `{"status": "healthy"|"degraded", "mode": "inline"|"opa_http"}` with correct values
    - Returns `degraded` when OPA is unreachable and fail_closed is False
    - Health-check respects configurable interval

### F5. Add OPA sidecar tests

- [ ] F5. Extend `tests/unit/test_policy_sidecar.py`
  - Exit criteria:
    - Test fail_closed=True raises error for compliance queries
    - Test fail_closed=False falls back for compliance queries
    - Test general queries always fall back
    - Test health-check returns correct statuses
    - Minimum 5 new test cases, all passing

---

## Lane G — Audit Trail Viewer

**Why**: AuditEvent records are persisted but have no surfacing beyond raw API. Finance regulations (SOX, SOC2, FINRA) require view, filter, and export of audit trails. This is a compliance visibility gap.

### G1. Add filtered/paginated audit event repository queries

- [ ] G1. Add `list_audit_events_filtered()` and `count_audit_events()` to `StorageRepository`
  - Exit criteria:
    - Filtered query supports: `event_type`, `resource_type`, `resource_id`, `limit`, `offset`, `sort_desc`
    - Pagination works correctly
    - `count_audit_events` returns correct total matching filters
    - Existing audit tests unchanged

### G2. Add API endpoints for audit events

- [ ] G2. Add `GET /v1/audit-events` and `GET /v1/audit-events/export` to API
  - Exit criteria:
    - `GET /v1/audit-events` returns paginated, filtered results with `{"items": [...], "total": N, "limit": N, "offset": N}`
    - `GET /v1/audit-events/export?format=csv` returns downloadable CSV
    - `GET /v1/audit-events/export?format=json` returns downloadable JSON array
    - All filter parameters combine correctly

### G3. Add CLI commands for audit listing and export

- [ ] G3. Add `audit list` and `audit export` commands to CLI
  - Exit criteria:
    - `audit list` outputs formatted JSON with same filters as API
    - `audit export --format csv --output events.csv` writes valid CSV file
    - Filtering identical to API

### G4. Add audit viewer tests

- [ ] G4. Create `tests/unit/test_audit_viewer.py`
  - Exit criteria:
    - Test filtered repository queries
    - Test pagination correctness
    - Test API endpoint structure
    - Test CSV export format
    - Test CLI audit list output
    - Minimum 6 new test cases

---

## Lane H — Reviewer Web UI

**Why**: Compliance officers and human reviewers need a graphical interface. The API/CLI-only workflow is not viable for regulated environments where non-technical staff perform review. Server-rendered, minimal-dependency approach.

### H1. Add Jinja2 template and static file support

- [ ] H1. Add `jinja2` dep, `templates/` directory, `static/` mount to API app
  - Exit criteria:
    - FastAPI app serves static CSS at `/static/`
    - `GET /ui/` routes render HTML templates
    - No JavaScript framework, no build step, no npm
    - Ruff/mypy clean with jinja2 stubs

### H2. Build review queue list page

- [ ] H2. Create `templates/review_list.html` with `GET /ui/review-queue` route
  - Exit criteria:
    - Table shows: fact_type, risk_level, review_state, dedup_count, created_at, evidence_count
    - Filter dropdowns: risk_level, fact_type, review_state
    - Sort by created_at (asc/desc), risk_level
    - Pagination controls
    - Each row links to detail page
    - No JavaScript required for basic function

### H3. Build review detail and action page

- [ ] H3. Create `templates/review_detail.html` with approve/reject actions
  - Exit criteria:
    - Detail page renders all review item fields
    - Approve button posts and redirects back to list
    - Reject button posts and redirects back to list
    - 404 shown for non-existent item
    - Flash message on successful action

### H4. Add web UI tests

- [ ] H4. Create `tests/unit/test_review_web_ui.py`
  - Exit criteria:
    - Test list page renders with items and empty state
    - Test detail page renders
    - Test approve/reject POST redirects
    - Test 404 for non-existent item
    - Minimum 5 test cases, all passing

---

## Lane K — Real LLM Integration (DeepSeek v4)

**Why**: Answer quality matters for finance decisions. The stub provider is fine for dev but production needs a real LLM. DeepSeek v4 provides cost-effective quality. LiteLLM adapter exists but needs hardening.

### K1. Add litellm as workspace dependency

- [ ] K1. Add `litellm>=1.50.0` to workspace dependencies, keep as lazy import
  - Exit criteria:
    - `uv sync` succeeds with litellm dependency
    - Stub provider works without litellm installed
    - LiteLLM provider works with litellm installed
    - mypy override added for litellm

### K2. Add DeepSeek v4 provider configuration

- [ ] K2. Add `litellm_deepseek_api_key` and `litellm_deepseek_base_url` to Settings
  - Exit criteria:
    - DeepSeek config propagates to `LiteLLMModelProvider` when model starts with `"deepseek/"`
    - Standard OpenAI models via litellm still work unchanged
    - `LJIT_MODEL_PROVIDER=litellm LJIT_LITELLM_MODEL=deepseek/deepseek-chat` works

### K3. Enhance prompt template for structured context

- [ ] K3. Restructure prompt in `LiteLLMModelProvider` with node role, score, provenance markers, and confidence band
  - Exit criteria:
    - Prompt includes node role, score, and provenance for each context item
    - Stub provider output updated to reflect new structure
    - LiteLLM provider sends enhanced prompt structure

### K4. Add prompt caching support

- [ ] K4. Add `litellm_prompt_caching_enabled: bool = False` to Settings
  - Exit criteria:
    - When enabled, caching params sent in completion kwargs
    - When disabled, no caching params (backward-compatible)

### K5. Add LLM integration tests

- [ ] K5. Extend `tests/unit/test_model_provider.py`
  - Exit criteria:
    - Test DeepSeek config propagation
    - Test enhanced prompt template structure
    - Test caching params when enabled
    - No regression on existing model tests
    - Minimum 3 new test cases

---

## Lane I — Full Isotonic Calibration Automation

**Why**: Confidence scores must be calibrated against actual human feedback for trust in finance AI. Currently `CalibrationService` is feedback-label CRUD only — labels are stored but never used to adjust confidence.

### I1. Implement isotonic regression fitting (PAVA algorithm)

- [ ] I1. Add `compute_calibration_curve()` and `apply_calibration()` to `CalibrationService`
  - Exit criteria:
    - PAVA algorithm implemented in pure Python (no scipy dependency)
    - Calibration curve computed from feedback labels: monotonically non-decreasing values
    - `apply_calibration` maps serving_confidence through the curve correctly
    - Edge cases handled: empty feedback, single label, already-monotonic labels

### I2. Add calibration step to governance scan

- [ ] I2. Wire calibration into `GovernanceService.run_governance_scan()`
  - Exit criteria:
    - Calibration curve computed from feedback labels during scan
    - Calibration applied to nodes NOT already decayed
    - Scan summary includes `calibrated_nodes` and `calibration_curve_segments`
    - Decay applied first, then calibration (does not override decay)

### I3. Add calibration tests

- [ ] I3. Extend `tests/unit/test_policy_and_governance.py`
  - Exit criteria:
    - Test PAVA algorithm on known input/output pairs
    - Test calibration curve from mixed feedback labels
    - Test `apply_calibration` with exact and interpolated values
    - Test governance scan applies calibration correctly
    - Test empty feedback does not crash
    - Minimum 4 new test cases

---

## Lane J — Full Load Shedding Automation

**Why**: High-volume knowledge systems in finance can produce thousands of review items. The current dedup-only approach means the queue grows without bound. Sampling and rate-based dropping are required for operational viability.

### J1. Implement sampling strategy in LoadSheddingService

- [ ] J1. Add `_should_sample()` with risk-based probabilities and tenant rate tracking
  - Exit criteria:
    - LOW risk items with `sample_rate=0.1` queued ~10% of the time
    - HIGH risk items always queued regardless of sample_rate
    - Tenant rate limiting works within configurable window
    - `sample_rate=1.0` queues everything (backward-compatible)
    - Sampling is deterministic for given inputs (testable)

### J2. Add configurable load shedding thresholds

- [ ] J2. Add `load_shedding_max_items_per_minute`, `load_shedding_window_seconds`, `load_shedding_enabled` to Settings
  - Exit criteria:
    - Load shedding respects configured max rate when enabled
    - Load shedding does nothing when disabled (default, backward-compatible)

### J3. Add load shedding tests

- [ ] J3. Extend `tests/unit/test_policy_and_governance.py`
  - Exit criteria:
    - Test sampling produces approximately correct rates
    - Test HIGH risk items never sampled out
    - Test tenant rate limiting
    - Test disabled load shedding queues everything
    - Minimum 4 new test cases

---

## Lane L — PDF Connector

**Why**: Regulatory filings, prospectuses, and contracts are predominantly PDF. Adding PDF ingestion unlocks the most important document type for finance knowledge bases.

### L1. Create PDF connector package scaffold

- [ ] L1. Create `packages/connectors/pdf/` following the git_local connector pattern
  - Exit criteria:
    - Workspace member `lattice-jit-connector-pdf` registered in pyproject.toml
    - `uv sync` recognizes the new package
    - Package imports: `from lattice_jit.connectors.pdf import PdfSnapshotService`

### L2. Implement PDF text extraction and node creation

- [ ] L2. Implement `PdfSnapshotService` with pypdf2-based text extraction
  - Exit criteria:
    - Single PDF file ingestion yields source snapshot with document node + page/section nodes
    - Directory of PDFs ingests each as separate subgraph
    - Text content extracted from each page
    - Non-PDF files in directory skipped with warning
    - `PdfIngestRequest` supports `page_mode` (document vs page-level nodes)

### L3. Wire PDF connector into API and CLI

- [ ] L3. Add `POST /v1/snapshots/pdf` endpoint and `ingest pdf` CLI command
  - Exit criteria:
    - API endpoint accepts PDF ingestion request and produces SnapshotResponse
    - CLI `ingest pdf` command mirrors `ingest git` behavior
    - Missing pypdf2 dependency handled with clear ImportError message

### L4. Add PDF connector tests

- [ ] L4. Create `tests/unit/test_pdf_connector.py`
  - Exit criteria:
    - Test PDF text extraction with programmatically-generated test PDF
    - Test single PDF and directory ingestion
    - Test page-mode splitting
    - Test API endpoint and CLI command parity
    - Minimum 4 test cases
    - No binary PDF files checked in

---

## Intersection Points and Sequencing Dependencies

```
Lane F (OPA)     — no deps — can start immediately
Lane G (Audit)   — no deps — can start immediately (parallel with F)
Lane K (LLM)     — no deps — can start immediately (parallel with F, G)
Lane H (Web UI)  — depends on G completed (audit queries for audit page)
Lane I (Calib.)  — depends on governance scan structure (already exists, extend it)
Lane J (Shed.)   — no hard deps but uses LoadSheddingService (already exists, extend)
Lane L (PDF)     — no deps — can start in parallel with any lane
```

**Recommended sequencing**:
1. **Phase 2a**: F1-F5 (OPA), G1-G4 (Audit), K1-K2 (LLM deps) — parallel
2. **Phase 2b**: H1-H4 (Web UI), K3-K5 (prompt + tests + caching)
3. **Phase 2c**: I1-I3 (Calibration), J1-J3 (Shedding), L1-L4 (PDF)

## Files to Create (New)

```
apps/api/src/lattice_jit/apps/api/templates/base.html
apps/api/src/lattice_jit/apps/api/templates/review_list.html
apps/api/src/lattice_jit/apps/api/templates/review_detail.html
apps/api/src/lattice_jit/apps/api/static/css/review.css
packages/connectors/pdf/pyproject.toml
packages/connectors/pdf/src/lattice_jit/connectors/pdf/__init__.py
packages/connectors/pdf/src/lattice_jit/connectors/pdf/service.py
packages/connectors/pdf/src/lattice_jit/connectors/pdf/py.typed
tests/unit/test_audit_viewer.py
tests/unit/test_review_web_ui.py
tests/unit/test_pdf_connector.py
```

## Risk Mitigation

1. **OPA fail-closed defaults to False**: backward-compatible; finance opts in explicitly.
2. **PAVA implementation**: ~40 lines pure Python, no scipy dependency.
3. **PDF connector**: `pypdf2` is lightweight. No OCR in first pass.
4. **Web UI**: server-rendered Jinja2, no frontend framework, no build step, no npm. Under 500 lines total.
5. **LiteLLM**: all new LLM features default to stub provider. Existing LiteLLM mock tests continue to pass.
6. **Load shedding**: opt-in via `load_shedding_enabled=False`.

## Phase 2 Definition of Done (Gate for v0.2.0)

All 7 lanes complete when:

- [ ] Lane F: OPA sidecar: 4+ Rego rules, fail-closed mode, health-check, docker-compose OPA, tests pass
- [ ] Lane G: Audit viewer: filtered/paginated API, CSV/JSON export, CLI, tests pass
- [ ] Lane H: Web UI: list page (filters, sort, pagination), detail page (approve/reject), tests pass
- [ ] Lane K: LLM: litellm dep, DeepSeek config, enhanced prompts, caching, tests pass
- [ ] Lane I: Calibration: PAVA regression, governance scan integration, tests pass
- [ ] Lane J: Shedding: sampling, rate-based dropping, configurable thresholds, tests pass
- [ ] Lane L: PDF: text extraction, node creation, API/CLI integration, tests pass
- [ ] `ruff check` exits 0, `mypy` exits 0, `pytest` exits 0 with no regressions
- [ ] Release tag v0.2.0 with gate results and test summary in `docs/releases/`
