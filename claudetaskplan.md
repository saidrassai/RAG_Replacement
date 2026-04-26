# Lattice-JIT Compiler v3.1 — Master Roadmap

> **Single source of truth** for all engineers and AI agents.
> Scope source: PLAN.md, README.md, and the six-round architecture design session (conv.md).
> Do not add components, skip tasks, or reorder phases without a written decision record.
> A task is complete **only** when every item in its exit criteria is verified.

---

## Conventions

| Symbol | Meaning |
|--------|---------|
| `[ ]` | Not started |
| `[x]` | Done — all exit criteria verified |
| `⚠️` | Risk — read before starting |
| `→ blocks` | Listed tasks cannot start until this task is complete |
| `OWNER` | `eng` engineer · `agent` AI coding agent · `ops` DevOps |

**Gate that applies to every task before closing it:**
```
ruff check   → exit 0, no output
mypy         → exit 0, no errors
pytest       → X passed, 0 failed, 0 skipped
```
If any gate fails, the task is not done regardless of other exit criteria.

---

## Architecture in One Paragraph

This system replaces RAG with a Knowledge Lattice: a directed graph of content-addressed,
immutable document nodes stored in Postgres, with build-system-style dependency invalidation,
deterministic MCP tool reads, compiled context slices cached in Redis by node-hash tuple,
and a governed write path for derived facts. A Policy Engine (OPA sidecar) evaluates before
every prompt call — not inside prompts. Answers carry full provenance: node hashes, snapshot
IDs, confidence bands, and conflict flags. No vector database. No embedding model. No chunking.

```
Knowledge Sources (Git · Confluence · SharePoint · PDF)
        │  ingest / snapshot
        ▼
 Knowledge Lattice (Postgres)
 nodes: immutable · content-hashed
 edges: typed · confidence-weighted · cycle-detected
        │
        ▼
 Policy Engine (OPA sidecar) ← evaluated BEFORE every prompt call
        │
        ▼
 Semantic Router + Multi-Subgraph Query Decomposer
        │
   ┌────┴────────────┬────────────────┐
   ▼                 ▼                ▼
Lane A (Hot)    Lane B (Resolve)  Lane C (Deep async)
Redis cache     Lattice compile   vLLM 3B · background
<10ms TTFT      MCP tool reads    enrichment + facts
   └────┬────────────┘
        ▼
 Context Compiler
 ToC at top · evidence at edges · compacted turns in middle
        │
        ▼
 Two-Phase Answering
 Phase A: provisional + confidence band (immediate)
 Phase B: conflict check + policy gate (async)
        │
        ▼
 Multi-Model Proxy (LiteLLM)
 distilled 7B (simple) · frontier 1M-ctx (synthesis)
        │
        ▼
 Answer + Full Provenance
 node hashes · snapshot IDs · confidence bands · conflict flags · audit trail

Control Planes (cross-cutting):
  Validity  — hash DAG · dirty propagation · build-system recompute
  Quality   — typed fact schema · adaptive decay · confidence calibration
  Cost      — token budget by data class · model tier routing
```

---

## Package Responsibility Map

| Package | Owns | Never owns |
|---------|------|------------|
| `contracts` | All Pydantic models, enums, shared types | Any business logic |
| `core` | Config, DI wiring, logging, IDs, error model, feature flags | Domain logic |
| `connectors/git_local` | Git snapshot ingestion, file extraction, source node creation | Lattice persistence |
| `lattice` | Graph persistence, traversal, cycle detection, dirty propagation, node ranking | Query orchestration |
| `runtime` | Router, decomposer, context compiler, token budgeting, Phase A+B orchestration | Lattice reads (delegates to `lattice`) |
| `governance` | Typed-fact validation, review queue, adaptive decay, audit events, calibration | Model calls |
| `policy` | Policy bundle evaluation — OPA adapter + local stub | Lattice or runtime logic |
| `storage` | SQLAlchemy models, migrations, repositories, Redis cache layer | Business logic |
| `model_proxy` | Model provider abstraction, deterministic stub, LiteLLM adapter | Context compilation |
| `apps/api` | HTTP entrypoints, request/response mapping, health endpoint | Business logic |
| `apps/cli` | Operator commands mirroring API flows | Business logic |
| `apps/worker` | Celery app setup, async job definitions | Business logic |

---

## Non-Negotiable Rules (All Engineers and Agents)

These are invariants. Code that violates them is a bug regardless of test results.

1. **`source_confidence` is immutable.** Set once at node creation, never updated. Calibration and decay update only `serving_confidence`.
2. **Never serve an unapproved derived fact.** Filter at the repository layer: `WHERE (requires_human_approval = false OR approved_at IS NOT NULL)`. Not at query time. Not in the API layer.
3. **Policy Engine is not optional.** No context compilation begins before a `PolicyBundle` is returned. OPA unavailable → HTTP 503, not fallback to stub.
4. **`provisional` is always explicit.** Every `AnswerEnvelope` has `provisional: true` or `provisional: false` set. Never omitted.
5. **Audit events are append-only.** No UPDATE or DELETE on `answer_events`. Corrections are new events.
6. **Cycle breaks are visible.** A broken cycle always produces a `conflict_flag` in the answer envelope. Silent resolution is forbidden.
7. **One task = one commit.** Do not batch tasks. Commit message format: `type(scope): description` (e.g. `fix(lint): import order in test_docker_compose`).
8. **Migrations are reviewed before merge.** Every Alembic migration must be read by a human or verified agent before landing on any shared environment. Auto-generated migrations are a starting point, not a final artifact.
9. **CI never makes live model calls.** `MODEL_PROVIDER=stub` is set explicitly in CI. Live model tests run only in the `integration-live` workflow, gated by manual trigger or release tag.

---

## Current State — Slice 1 Complete

Verified complete at initial commit. Do not re-implement any of these.

- [x] Monorepo structure: `apps/`, `packages/`, `ops/`, `tests/`, `docs/`
- [x] `packages/contracts` — `KnowledgeNode`, `KnowledgeEdge`, `PolicyBundle`, `CompiledContextManifest`, `AnswerEnvelope`, `ReviewItem`, all enums, `tenant_id` on every model
- [x] `packages/storage` — SQLAlchemy models + migrations for all nine tables
- [x] `packages/core` — config, DI, logging, IDs, error model
- [x] `packages/lattice` — graph persistence, basic traversal
- [x] `packages/runtime` — router adapter (stub), context compiler (stub), Phase A orchestrator
- [x] `packages/governance` — contracts and storage scaffolded
- [x] `packages/policy` — local inline evaluator (stub), OPA bundle scaffold in `ops/opa/`
- [x] `packages/model_proxy` — deterministic stub provider, LiteLLM adapter wired but not default
- [x] `packages/connectors/git_local` — local Git snapshot ingest
- [x] `apps/api` — four endpoints with stub responses
- [x] `apps/cli` — mirrors API: ingest, query, answer-status, review-list
- [x] `apps/worker` — Celery app, placeholder jobs
- [x] `ops/docker` — Docker Compose: Postgres + Redis + API + worker
- [x] `ops/opa` — policy bundle scaffold
- [x] `docs/` — architecture.md, interfaces.md, adr-001-modular-monorepo.md
- [x] 15/15 tests passing (1 skipped — Docker e2e, env constraint)

---

## Lane A — First-Slice Closure
*Prerequisite: None. Start here.*

---

### A1 — Fix lint import order
**OWNER:** eng/agent | **Priority:** Critical | **Blocks:** everything

```bash
uv run ruff check --fix tests/e2e/test_docker_compose.py
uv run ruff check
```

**Exit criteria:**
- `uv run ruff check` exits 0 with zero output.

---

### A2 — Unblock Docker e2e test
**OWNER:** ops/eng | **Priority:** Critical | **Depends on:** A1 | **Blocks:** B1

Identify the process holding port 8000 (`sudo lsof -i :8000`). Either terminate
it or change the API port in `ops/docker/docker-compose.yml` to an unused port
(e.g. 8001). Update `.env.example` to document the chosen port.

**Exit criteria:**
- `docker compose -f ops/docker/docker-compose.yml up --build` completes with
  all four containers running and zero port-bind errors.
- `uv run --all-packages pytest` shows X passed, **0 skipped**, 0 failed.

---

### A3 — Move root SVG diagrams to docs/
**OWNER:** eng/agent | **Priority:** Medium | **Depends on:** None

Move `lattice_jit_v3_governance.svg` and `lattice_jit_v3_runtime.svg` from repo
root to `docs/diagrams/`. Update all references in `docs/architecture.md`.

**Exit criteria:**
- No SVG files exist at repo root.
- `docs/architecture.md` renders diagram references without broken links.
- All three gates pass.

---

### A4 — Add architecture rationale to README
**OWNER:** eng | **Priority:** Medium | **Depends on:** A3

Add this section to `README.md` immediately after Quick Start:

```markdown
## Architecture

This system replaces RAG with a Knowledge Lattice — a directed graph of
content-addressed document nodes with dependency-aware cache invalidation.
See docs/architecture.md for the full design.

Key concepts:
- **Nodes**: immutable, content-addressed document sections
- **Edges**: typed, confidence-weighted (supersedes/implements/contradicts/cites/weak-ref)
- **Compiled slices**: assembled context prompts cached in Redis by node-hash tuple
- **Write path**: dirty propagation rebuilds only affected slices on source change
- **Policy gate**: OPA evaluation before every prompt call — never inside prompts
```

**Exit criteria:**
- README contains the section above verbatim (content, not formatting).
- Quick Start section is unchanged.
- All three gates pass.

---

## Lane B — First-Slice Release Gates
*Prerequisite: A1, A2 complete.*

---

### B1 — Capture and record quality gate outputs
**OWNER:** eng | **Priority:** High | **Depends on:** A1, A2

Run all gates and record results in `docs/releases/v0.1.0-slice1.md`:

```markdown
# Release v0.1.0 — First Slice

Date: YYYY-MM-DD
Commit: <sha>

Gates:
  ruff:   PASS
  mypy:   PASS
  pytest: X passed, 0 failed, 0 skipped

Docker Compose boot: PASS (all 4 containers healthy)
API endpoints verified: POST /v1/snapshots/git, POST /v1/queries,
                        GET /v1/answers/{id}, GET /v1/review-queue
CLI commands verified: ingest git, query, answer get, review list
```

**Exit criteria:**
- `docs/releases/v0.1.0-slice1.md` exists with all fields filled.

---

### B2 — Freeze first-slice API/CLI contract baseline
**OWNER:** eng | **Priority:** High | **Depends on:** B1

Verify every endpoint and CLI command listed in `docs/interfaces.md` matches
the current implementation. If any endpoint returns a response that does not
match the contract schema in `packages/contracts`, that is a bug to fix before
tagging — not something to update the contract around.

**Exit criteria:**
- All four HTTP endpoints respond with schemas that validate against `contracts` models.
- All four CLI commands execute without error against the running stack.
- `docs/interfaces.md` accurately reflects current behavior (update if drifted).

---

### B3 — Tag first-slice release
**OWNER:** eng | **Priority:** High | **Depends on:** B2, A3, A4

```bash
git tag -a v0.1.0 -m "First slice: core scaffold, contracts, storage, git ingest, stub runtime"
git push origin v0.1.0
```

**Exit criteria:**
- Tag `v0.1.0` exists on `main` and is pushed to remote.
- `→ blocks` Lane C start.

---

## Lane C — Phase 2 Core Implementation
*Prerequisite: B3 complete. Implement tasks in order — each depends on the previous.*

⚠️ **C1 must be done before C2.** Governance and calibration work (Lane E) requires
real model outputs. Building against a stub only allows wiring failures to pass silently.

---

### C1 — Activate LiteLLM runtime path
**OWNER:** eng/agent | **Priority:** Critical | **Depends on:** B3

**Part 1 — Environment config.**
Add to `.env.example`:
```
MODEL_PROVIDER=litellm
LITELLM_MODEL=gpt-4o-mini          # or ollama/llama3.1:8b for local
LITELLM_API_KEY=sk-...             # blank for Ollama
LITELLM_API_BASE=                  # http://localhost:11434 for Ollama
```

**Part 2 — Switch default provider.**
In `packages/model_proxy`, activate LiteLLM when `MODEL_PROVIDER=litellm`.
Stub remains default when env var is absent (preserves CI behaviour).

The LiteLLM adapter must return a fully populated `AnswerEnvelope`, not raw text:
- `provenance[]` populated from the manifest's node refs
- `confidence_band` computed as `min/max/mean` of `serving_confidence` across manifest nodes
- `provisional: True` on all Phase A responses

**Part 3 — Fix stub to return structured provenance.**
The stub must return a realistic `AnswerEnvelope` with `provenance` entries
populated from `manifest.node_refs`. A stub returning only `{"text": "stub"}` is
a bug — it allows broken provenance wiring to pass tests invisibly.

**Part 4 — CI gate.**
Add a GitHub Actions workflow at `.github/workflows/ci.yml` that:
- Sets `MODEL_PROVIDER=stub` explicitly
- Runs `ruff check`, `mypy`, `pytest` on every push and PR
- Completes in under 5 minutes

Add a separate `.github/workflows/integration-live.yml` that:
- Runs only on manual trigger (`workflow_dispatch`) or release tags
- Uses a secrets-stored API key
- Runs tests marked `@pytest.mark.live`

**Exit criteria:**
- `MODEL_PROVIDER=stub` → all existing tests pass, no live model calls.
- `MODEL_PROVIDER=litellm` with a live key → `POST /v1/queries` returns
  `AnswerEnvelope` with non-empty `provenance[]` (verified manually or via
  a VCR-cassette integration test).
- Stub returns `AnswerEnvelope` with `len(provenance) == len(manifest.node_refs)`.
- `.github/workflows/ci.yml` exists and is syntactically valid.

---

### C2 — Implement lattice differ (dirty propagation)
**OWNER:** eng | **Priority:** Critical | **Depends on:** C1

**Step 1 — Contract change (do this first, before any graph code).**
In `packages/contracts`, add to `KnowledgeEdge`:
```python
cycle_break: bool = False
cycle_break_reason: str | None = None
```
Add an Alembic migration. Run `alembic upgrade head` and verify it completes.

**Step 2 — Cycle detection.**
In `packages/lattice`, use `networkx.simple_cycles` on the subgraph being
traversed (not the full graph). When a cycle is detected:
1. Find the lowest-confidence edge in the cycle.
2. Set `cycle_break=True`, `cycle_break_reason=f"cycle broken: confidence={edge.confidence:.2f}"`.
3. Persist the updated edge.
4. Add a `conflict_flag` to the compiled manifest.

**Step 3 — Lattice Differ.**
When a new Git snapshot is ingested (new commit ref), compute changed files with
`git diff --name-only <old_hash> <new_hash>`. For each changed file:
1. Find all `KnowledgeNode` records with matching `source_path`.
2. Run this recursive CTE to find all downstream dependents:
```sql
WITH RECURSIVE downstream AS (
    SELECT target_node_id AS node_id FROM knowledge_edges
    WHERE source_node_id = :changed_node_id
  UNION
    SELECT e.target_node_id FROM knowledge_edges e
    JOIN downstream d ON e.source_node_id = d.node_id
)
SELECT node_id FROM downstream;
```
3. Set `validity_state = 'dirty'`, `dirtied_at = now()` on all affected nodes.
4. Enqueue Celery task `recompile_dirty_nodes` per node, priority-weighted by `access_frequency`.

**Exit criteria:**
- Migration runs cleanly: `alembic upgrade head` exits 0 on a fresh DB.
- Unit test: a 3-node cycle (A→B→C→A) resolves with a break at lowest-confidence
  edge; resulting traversal is acyclic.
- Unit test: changing one source file marks exactly the correct downstream nodes
  dirty and leaves upstream nodes at `validity_state = 'valid'`.
- Unit test: `cycle_break=True` persists to DB and is re-read correctly.

---

### C3 — Wire cache invalidation to dirty propagation
**OWNER:** eng/agent | **Priority:** Critical | **Depends on:** C2

Cache keys are `compiled:{sha256("|".join(sorted(node_hashes)))}`.

On every cache write, store a reverse mapping in Redis:
```
SET node_hash_idx:{node_hash} → SET of cache_keys   (with TTL matching cache entry)
```

When C2 marks a node dirty, look up `node_hash_idx:{node_hash}` and delete all
referenced cache keys. Clean up the reverse-index key after deletion.

**Exit criteria:**
- Integration test: warm a cache entry → mark one constituent node dirty →
  the cache entry is gone from Redis in the same request cycle.
- Integration test: cache entries for nodes NOT in the dirty set survive unaffected.
- Unit test: reverse-index key is deleted after the cache entry it references is evicted.

---

### C3b — Implement recompile Celery task
**OWNER:** eng/agent | **Priority:** Critical | **Depends on:** C3

In `apps/worker`, implement `recompile_dirty_nodes`:
1. Fetch the dirty node and its full ancestor chain.
2. Assemble a new `CompiledContextManifest` from the new snapshot content.
3. Persist manifest + compiled items to DB.
4. Warm Redis cache with the new compiled slice.
5. Set `validity_state = 'valid'`.
6. Write `answer_event` of type `recompiled` with old and new manifest IDs.

**Exit criteria:**
- Integration test: after C2 dirty propagation, the task runs and the node
  reaches `validity_state = 'valid'` with a new manifest ID.
- Failed recompilation sets `validity_state = 'recompile_failed'` — never 'valid'.
  The system does not serve a stale or empty cache entry on failure.

---

### C4 — Implement multi-subgraph query decomposition
**OWNER:** eng | **Priority:** High | **Depends on:** C3b

In `packages/runtime`, extend the router adapter:

**Decomposer output:** `List[SubgraphTarget]` where each has
`subgraph_id`, `confidence`, `intent_label`.

**Algorithm:**
1. Run semantic router against all registered routes.
2. Collect routes with `confidence >= SUBGRAPH_CONFIDENCE_THRESHOLD` (default: 0.60, tenant-configurable via policy bundle).
3. If zero routes exceed threshold, fall back to the single highest-confidence route.

**Compiler behaviour with multiple subgraphs:**
1. Run parallel lattice traversals per subgraph target.
2. Assemble composite context: cross-subgraph summary (≤500 tokens) at top, then subgraph slices in confidence-descending order.
3. If total token count exceeds policy-bundle budget, truncate lower-confidence subgraphs first. Never truncate the highest-confidence subgraph.

**Exit criteria:**
- Unit test: query decomposing to two routes above threshold → two `SubgraphTarget` entries.
- Unit test: only one route above threshold → one target.
- Unit test: composite context exceeding budget is truncated at the correct subgraph boundary, never mid-node.
- Integration test: `POST /v1/queries` with a multi-intent query returns a manifest
  with nodes from two distinct subgraph IDs in `provenance[]`.

---

## Lane D — Test Expansion
*Tasks in this lane run in parallel with their dependency's completion, not after all of Lane C.*

---

### D1 — Tests: lattice differ and selective cache invalidation
**OWNER:** eng/agent | **Priority:** High | **Depends on:** C2, C3

Write the full write-path integration test:
ingest snapshot v1 → run query → confirm cache warm → ingest snapshot v2
(one file changed) → verify: changed node dirty, cache entry evicted, unrelated
cache entries intact, recompile task runs, node returns to valid, re-query
returns new content.

**Exit criteria:**
- The above test exists and passes.
- Test count increases by at least 5 from the C2/C3 unit tests already written.

---

### D2 — Tests: LiteLLM active path
**OWNER:** eng/agent | **Priority:** Medium | **Depends on:** C1

Write a VCR-cassette integration test that records a real LiteLLM call once
and replays it in CI without a live key. Verify the response is a valid
`AnswerEnvelope` with structured `provenance[]`.

**Exit criteria:**
- Test exists, is tagged `@pytest.mark.vcr`, and passes in CI with no live call.

---

### D3 — Tests: multi-subgraph integration
**OWNER:** eng/agent | **Priority:** Medium | **Depends on:** C4

Create a fixture with two knowledge domains (e.g. "policy" and "code").
Submit a query that triggers both. Verify merged provenance contains entries
from both domains and the cross-subgraph summary appears at the top of the manifest.

**Exit criteria:**
- Test exists and passes.
- `provenance[]` in the response references node IDs from two distinct subgraph IDs.

---

### D4 — Tests: OPA sidecar integration
**OWNER:** eng/agent | **Priority:** Medium | **Depends on:** E3

⚠️ **This task depends on E3 (OPA sidecar enforcement), which is in Lane E.**
Do not mark D4 complete until E3 is complete.

Write a test that:
1. Boots the OPA sidecar (in Docker Compose test profile).
2. Submits a query against a PHI-tagged node.
3. Verifies the returned `PolicyBundle` has `required_human_gate: True`.
4. Shuts down the OPA sidecar and verifies the API returns HTTP 503.

**Exit criteria:**
- Test exists and passes with the OPA sidecar running.
- HTTP 503 is verified on sidecar failure — not a fallback to stub.

---

## Lane E — Deferred-by-Plan Items
*These were explicitly deferred in PLAN.md. Each must either ship with verified
exit criteria OR be formally removed from scope with a written decision record
in `docs/decisions/`. Neither outcome is optional — deferred does not mean forgotten.*

---

### E1 — Full isotonic confidence calibration
**OWNER:** eng | **Priority:** Medium | **Depends on:** C1

**What:** Implement the weekly Celery beat job that fits `sklearn.isotonic.IsotonicRegression`
per domain on `feedback_labels` and updates `serving_confidence` on active nodes.

Add `POST /v1/answers/{answer_id}/feedback` endpoint:
```json
{ "label": "correct|incorrect|partial", "reviewer_id": "string", "notes": "string|null" }
```

**Calibration algorithm:**
1. Fetch `feedback_labels` from past 90 days joined with `AnswerEnvelope.confidence_band.mean`.
2. Encode: `correct=1.0`, `incorrect=0.0`, `partial=0.5`.
3. Fit isotonic regression on `(predicted_confidence, correctness)` pairs.
4. **Minimum sample gate:** fewer than 50 samples → skip, log warning, write no map.
5. Persist calibration map to `confidence_calibration_maps` with `domain`, `fitted_at`, `sample_count`.
6. Bulk-update `serving_confidence` via calibration map. Never touch `source_confidence`.

**Exit criteria:**
- Unit test: 100-sample synthetic dataset produces a map that reduces mean calibration error vs. raw confidence.
- Unit test: <50 samples → calibration skipped, warning logged, no map written.
- Integration test: full cycle — label some answers → run calibration → verify `serving_confidence` updated, `source_confidence` unchanged.
- Calibration run writes `calibration_run_complete` audit event with domain, sample count, map hash.

---

### E2 — Full reviewer load shedding automation
**OWNER:** eng | **Priority:** Medium | **Depends on:** E1

Three-step pipeline before any derived fact enters the review queue:

**Step 1 — Semantic deduplication:**
Compare incoming fact's typed fields against all pending queue items of the same
`fact_type`. If `fact_fields` match exactly on all required fields, set
`duplicate_of = existing_review_item_id`, append session ID to existing item,
skip insertion.

**Step 2 — Batch grouping:**
Queue items of the same `fact_type` from the same `source_node_hash` set share
a `batch_id`. `review list` shows them grouped with a count.
`review approve <batch_id>` approves all items in the batch.

**Step 3 — Auto-approval:**
If `fact_type` is in tenant's `auto_approve_types` (OPA policy, default:
`["owner", "api_signature"]`) AND `serving_confidence >= 0.75`:
- Set `approved_at = now()`, `auto_approved = True`, skip queue.
- Write `derived_fact_auto_approved` audit event.
- Flag 5% of auto-approved facts for retrospective human review via
  `retrospective_sample` table (does not block serving).

**Exit criteria:**
- Unit test: duplicate fact → not inserted, existing item's session list extended.
- Unit test: two facts from same source node hash → same `batch_id`.
- Unit test: `owner` fact at `serving_confidence=0.80` → auto-approved when `auto_approve_types` includes `owner`.
- Unit test: `constraint` fact at any confidence → never auto-approved.
- Integration test: 20 equivalent `owner` facts → 1 queue item, 19 duplicates,
  `review list` shows count=19.

---

### E3 — Full OPA sidecar enforcement path
**OWNER:** ops/eng | **Priority:** Medium | **Depends on:** C1

⚠️ **This is a dependency of D4. Resolve this before D4 can close.**

Switch `packages/policy` default from local inline evaluator to OPA sidecar
in all non-test environments.

OPA sidecar added to `ops/docker/docker-compose.yml`. Policy bundle in `ops/opa/`.

The policy adapter POSTs to `http://opa:8181/v1/data/lattice/policy/allow` and
parses the response into a `PolicyBundle`. This call is synchronous and must
complete before any context compilation.

Write OPA rules for:
- PHI-tagged nodes → `required_human_gate: true` + redaction patterns for identifiers
- PCI-tagged nodes → `allowed_tools` read-only only, `max_token_budget: 50000`
- Default → no gate, standard budget

OPA sidecar down → policy adapter returns DENY, API returns HTTP 503.
Never fall back to the inline stub in a non-test environment.

**Exit criteria:**
- Integration test: PHI-tagged node query → `PolicyBundle` has `required_human_gate: True`.
- Integration test: PCI-tagged node query → compiled context ≤ 50,000 tokens enforced.
- Integration test: OPA sidecar down → HTTP 503, not inline-stub fallback.
- Unit test: redaction patterns applied to compiled context before model call
  — raw pattern string absent from manifest.

---

### E4 — Reviewer web UI decision
**OWNER:** eng | **Priority:** Medium | **Depends on:** None

Evaluate whether a reviewer web UI is needed, given the CLI already surfaces
`review list`, `review approve`, and `review reject`.

Decision options:
- **Ship it:** Implement a minimal read-only web UI showing the review queue
  with approve/reject buttons. Document implementation in `docs/decisions/E4-reviewer-ui.md`.
- **Descope it:** Write a decision record in `docs/decisions/E4-reviewer-ui.md`
  explaining why the CLI is sufficient and the UI will not be built.

**Exit criteria:**
- `docs/decisions/E4-reviewer-ui.md` exists with a clear decision and rationale.
- If shipped: the UI is accessible from the Docker Compose stack and the basic
  approve/reject flows work.

---

## Lane F — Governance and Observability
*Prerequisite: Lane C complete. These tasks add the production-grade control
planes. Implement in order.*

---

### F1 — Implement typed-fact schema enforcement
**OWNER:** eng/agent | **Priority:** High | **Depends on:** C3b

The compaction daemon (Lane C, Watch Path) may only write nodes of these types.
Any other type raises `ValidationError` and writes nothing.

| Type | Required fields |
|------|----------------|
| `decision` | `date`, `owner`, `source_node_hash` |
| `constraint` | `regulation_ref`, `effective_date` |
| `api_signature` | `service`, `version`, `schema_hash` |
| `owner` | `contact`, `since` |
| `incident` | `severity`, `resolution_node_id` |

Every derived node created with:
- `source_confidence: 1.0` (immutable)
- `serving_confidence: 0.70` (mutable via calibration/decay)
- `ttl_days`: per fact type (see F2)
- `requires_human_approval: bool` — from policy bundle at extraction time
- `approved_at: datetime | None` — null until approved
- `auto_approved: bool = False`

**Exit criteria:**
- Unit test: unrecognised fact type → `ValidationError`, nothing written to DB.
- Unit test: valid `decision` node persisted with all required fields.
- Unit test: `source_confidence` cannot be changed after creation (DB constraint or application guard — document which).

---

### F2 — Implement adaptive decay GC
**OWNER:** eng | **Priority:** High | **Depends on:** F1

**Default TTL and volatility rules:**

| Fact type | Default TTL | Revalidation trigger |
|-----------|-------------|----------------------|
| `api_signature` | 30 days | Any commit touching the API schema file |
| `decision` | 180 days | Policy-update node ingested |
| `constraint` | 365 days | Policy-update node ingested — mandatory |
| `owner` | 90 days | None |
| `incident` | 60 days | Unused 30 days → decay 50% |

**Volatility adjustment (learned from Git history, not declared):**
Observe actual commit frequency for source file types over the past 90 days.
If 2× higher than default TTL baseline → halve effective TTL.
If 2× lower → extend by 50%. Cap at per-type min/max bounds.

**GC worker (Celery beat, weekly):**
1. For each `serving_confidence` node past effective TTL:
   - `access_count_30d == 0` → delete node and its review queue entry.
   - `access_count_30d > 0` and `serving_confidence > 0.40` → decay `serving_confidence` by 0.05, extend TTL 7 days.
   - `serving_confidence ≤ 0.40` → move to quarantine for human review.
2. For any `constraint` node whose policy source has a new version →
   set `validity_state = 'revalidation_required'` immediately, regardless of TTL.

**Exit criteria:**
- Unit test: `api_signature` with 3× observed commit frequency → TTL halved.
- Unit test: node with `access_count_30d == 0` past TTL → deleted by GC.
- Unit test: node at `serving_confidence = 0.45` → decayed to 0.40 by one GC pass.
- Unit test: node at `serving_confidence = 0.40` → moved to review queue, not deleted.
- Integration test: GC worker run processes a fixture node set and produces expected outcomes.

---

### F3 — Implement audit event writing
**OWNER:** eng/agent | **Priority:** High | **Depends on:** F1

Every significant event written to `answer_events` (append-only, no UPDATE, no DELETE).

| Event type | Triggered by | Required payload |
|------------|-------------|-----------------|
| `query_received` | `POST /v1/queries` | `query_text`, `tenant_id`, `snapshot_id` |
| `policy_evaluated` | Policy engine | `policy_bundle_hash`, `gate_triggered` |
| `context_compiled` | Context compiler | `manifest_id`, `node_hashes[]`, `token_count` |
| `phase_a_answered` | Phase A complete | `answer_id`, `confidence_band`, `provisional` |
| `phase_b_answered` | Phase B complete | `answer_id`, `conflict_flags[]`, `gate_passed` |
| `node_dirtied` | Lattice differ | `node_id`, `source_change_hash` |
| `node_recompiled` | Recompile task | `node_id`, `old_manifest_id`, `new_manifest_id` |
| `derived_fact_extracted` | Compaction daemon | `node_id`, `fact_type`, `session_id` |
| `derived_fact_approved` | Reviewer | `node_id`, `reviewer_id` |
| `derived_fact_rejected` | Reviewer | `node_id`, `reviewer_id` |
| `derived_fact_auto_approved` | Load shedding | `node_id`, `serving_confidence` |
| `confidence_decayed` | GC worker | `node_id`, `old_confidence`, `new_confidence` |
| `calibration_run_complete` | Calibration job | `domain`, `sample_count`, `map_hash` |

Audit event payload is JSONB. Answer text does NOT go in audit events — only metadata.

**Exit criteria:**
- Integration test: a full query cycle (ingest → query → Phase A → Phase B) produces
  exactly the expected audit events in the correct order.
- Unit test: the application DB user has no UPDATE or DELETE permission on `answer_events`
  (verified via `pg_roles` or an attempt that raises `PermissionError`).

---

### F4 — Implement two-phase answering
**OWNER:** eng | **Priority:** High | **Depends on:** F3

**Phase A** (already scaffolded — make it real):

`ConfidenceBand` computed as:
```python
confidences = [node.serving_confidence for node in manifest.nodes]
ConfidenceBand(min=min(c), max=max(c), mean=sum(c)/len(c))
```

If `min < 0.60` → `provisional=True` + `conflict_flag: "LOW_CONFIDENCE"`.

**Phase B** (async Celery task, triggered when `PolicyBundle.phase_b_required` or Phase A `provisional=True`):

Three checks:
1. **Cross-subgraph consistency:** send Phase A answer + all subgraph context to model. Prompt: `"List factual contradictions between this answer and the source context. Return [] if none."` Parse as `List[ContradictionFlag]`.
2. **Cycle-break path verification:** if manifest contains nodes reached through a `cycle_break` edge, verify the alternative path produces a consistent answer. If not → `CYCLE_AMBIGUITY` conflict flag.
3. **Policy gate:** re-evaluate `PolicyBundle` against Phase A answer text. Apply redaction patterns. If any pattern matches → redact + set `answer_modified_by_policy: True`.

Phase B updates the `AnswerEnvelope` (now `phase: "B"`, `status: "complete"` or `"failed"`).
Phase B failure → `phase_b_status: "failed"` — Phase A answer survives and remains readable.

Polling: `GET /v1/answers/{answer_id}` returns Phase A immediately, Phase B when ready.
Add `Retry-After: 5` response header when `phase_b_status == "pending"`.

**Exit criteria:**
- Unit test: all manifest nodes `serving_confidence >= 0.80` → `provisional=False`, no LOW_CONFIDENCE flag.
- Unit test: one node at `serving_confidence=0.55` → `provisional=True`, LOW_CONFIDENCE flag present.
- Unit test: cross-subgraph contradiction detected and added as conflict flag.
- Unit test: redaction pattern match in Phase A → redacted in Phase B, `answer_modified_by_policy=True`.
- Unit test: Phase B failure → `phase_b_status: "failed"`, Phase A answer intact.
- Integration test: Phase B completes and updates envelope within 30 seconds (SLO checkpoint).
- Integration test: polling endpoint returns Phase A before Phase B, Phase B after.

---

### F5 — Implement observability and SLO monitoring
**OWNER:** ops/eng | **Priority:** High | **Depends on:** F4

Add Prometheus metrics using `prometheus-fastapi-instrumentator` for API,
manual instrumentation for worker tasks.

Required metrics:

| Metric | Type | Labels |
|--------|------|--------|
| `lattice_query_duration_seconds` | Histogram | `lane`, `tenant_id`, `phase` |
| `lattice_cache_hit_ratio` | Gauge | `tenant_id` |
| `lattice_dirty_nodes_total` | Gauge | `domain` |
| `lattice_recompile_queue_depth` | Gauge | `priority` |
| `lattice_phase_b_duration_seconds` | Histogram | `tenant_id` |
| `lattice_confidence_band_mean` | Histogram | `domain` |
| `lattice_review_queue_depth` | Gauge | `tenant_id` |
| `lattice_calibration_sample_count` | Gauge | `domain` |

Add `/metrics` endpoint to `apps/api`.

Write SLO targets and alert rules:

| SLO | Target |
|-----|--------|
| Lane A p95 latency | < 50ms (5-min window) |
| Lane B p95 latency | < 3s (5-min window) |
| Phase B p95 latency | < 30s (15-min window) |
| Cache hit ratio | > 70% (1-hour window) |
| Dirty node backlog | < 500 (instantaneous) |
| Review queue depth | < 200 (instantaneous) |

Write `ops/monitoring/slo.yaml` and `ops/monitoring/alerts.yaml`.

**Exit criteria:**
- `curl http://localhost:8000/metrics` returns valid Prometheus exposition format.
- All eight metrics present after a single end-to-end query.
- `promtool check rules ops/monitoring/alerts.yaml` exits 0.
- Load test (50 concurrent users, 1 query/sec, 5 minutes): Lane A p95 < 50ms,
  Lane B p95 < 3s. Results documented in `docs/load-test-results.md`.
  If targets not met: document the bottleneck and open a GitHub issue tagged
  `performance` before proceeding.

---

## Lane G — Additional Connectors
*Prerequisite: Lane F complete. Each connector must implement `BaseConnector`
from `packages/connectors/git_local` — same snapshot contract, same node
creation pattern, same hash scheme.*

---

### G1 — PDF connector
**OWNER:** eng/agent | **Priority:** Medium

`packages/connectors/pdf`. Use `pdfplumber`.

One `KnowledgeNode` per page. Node hash: `sha256(page_text + pdf_sha256 + page_number)`.
Section headings detected via font-size heuristics → `implements` edges from section nodes to page nodes.

**Exit criteria:**
- Integration test: ingest 10-page PDF → 10+ nodes with correct hashes.
- Integration test: re-ingest same PDF → idempotent, no new nodes.
- Integration test: re-ingest with one page changed → only that page's node dirtied.

---

### G2 — Confluence connector
**OWNER:** eng | **Priority:** Medium

`packages/connectors/confluence`. Confluence REST API v2.

One node per page. Hash: `sha256(page_body + page_version_id)`.
`supersedes` edge when `version.number` increments.

**Exit criteria:**
- Integration test (VCR cassette): ingest test space → nodes and edges correct.
- Integration test: page updated → old node dirty, new node with `supersedes` edge.

---

### G3 — SharePoint connector
**OWNER:** eng | **Priority:** Medium

`packages/connectors/sharepoint`. Microsoft Graph API.

Supported file types: `.docx`, `.pdf` (delegate to G1), `.txt`, `.md`.
Hash: `sha256(file_content + file_eTag)`.
`supersedes` edge when eTag changes.

**Exit criteria:**
- Integration test (VCR cassette or mock Graph API): ingest → nodes correct.
- Integration test: file updated → old node dirty, new node with `supersedes` edge.

---

## Lane H — Multi-Tenancy Hardening
*Prerequisite: Lane G complete. `tenant_id` exists on all tables since Slice 1.
This phase enforces isolation at the data layer.*

---

### H1 — Postgres Row Level Security
**OWNER:** ops/eng | **Priority:** High

```sql
ALTER TABLE knowledge_nodes ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON knowledge_nodes
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

Apply to every table with `tenant_id`. Application sets `app.tenant_id` at
DB session start:
```python
session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
```

**Exit criteria:**
- Integration test: tenant A query cannot read tenant B nodes via application DB user.
- Integration test: application DB user does NOT have `BYPASSRLS` privilege.

---

### H2 — Redis key namespacing
**OWNER:** eng/agent | **Priority:** High | **Depends on:** H1

All Redis keys prefixed `tenant:{tenant_id}:`. Enforced in `packages/storage` cache layer.

**Exit criteria:**
- Unit test: cache write for tenant A uses correct prefix.
- Unit test: tenant A cache read cannot retrieve tenant B entries.

---

## Lane I — Ship Readiness
*Prerequisite: Lanes E, F, G, H all complete (or formally descoped).*

---

### I1 — Release checklist document
**OWNER:** eng | **Priority:** High

Write `docs/releases/production-checklist.md` covering:
- Bootstrap: DB migration sequence, required env vars, secret rotation steps
- Health check sequence: Postgres → Redis → OPA → API → worker
- Smoke test suite: which tests to run to confirm a deployment is live
- Rollback procedure: step-by-step, tested at least once in non-prod

**Exit criteria:**
- Document exists with all four sections complete.
- Rollback procedure has been executed in a staging environment and the result documented.

---

### I2 — Minimum observability smoke check
**OWNER:** ops/eng | **Priority:** High | **Depends on:** I1

Verify in the production deployment:
- Every request gets a unique `request_id` in logs and response headers.
- Answer IDs are queryable from `answer_events` within 5 seconds of response.
- Provenance node hashes in responses match records in `knowledge_nodes`.

**Exit criteria:**
- Runbook in `docs/releases/production-checklist.md` documents how to verify each.
- Automated smoke test script exists at `ops/smoke/smoke.sh` and completes in < 60 seconds.

---

### I3 — Cut production release tag
**OWNER:** eng | **Priority:** High | **Depends on:** I1, I2, all Lane E items resolved

```bash
git tag -a v1.0.0 -m "Production release: Lattice-JIT Compiler v3.1"
git push origin v1.0.0
```

**Exit criteria:**
- All Lane E items are either `[x]` complete or have a decision record in `docs/decisions/`.
- All quality gates pass: `ruff`, `mypy`, `pytest` exit 0.
- Release notes exist in `docs/releases/v1.0.0.md` with gate results and component inventory.
- Tag `v1.0.0` is on `main` and pushed to remote.

---

## Definition of Project Complete

The project is complete when **all** of the following are true:

- [ ] Tag `v0.1.0` exists (first-slice release — Lane B complete)
- [ ] Tag `v1.0.0` exists (production release — Lane I complete)
- [ ] Lane E: every item is either `[x]` verified or has a written decision record in `docs/decisions/`
- [ ] `ruff check` exits 0
- [ ] `mypy` exits 0
- [ ] `pytest` exits 0 with 0 skipped
- [ ] `docs/releases/production-checklist.md` exists
- [ ] `ops/monitoring/slo.yaml` and `ops/monitoring/alerts.yaml` exist and pass `promtool check`
- [ ] Load test results documented in `docs/load-test-results.md`
- [ ] No open GitHub issues tagged `blocker`

---

## Phase Completion Record Template

Fill this in before declaring any lane complete:

```
Lane [X] — [Name] — DONE
=========================
Completed by: [name or agent ID]
Date: YYYY-MM-DD
Commit range: [first]..[last]

Gates:
  ruff:   PASS
  mypy:   PASS
  pytest: X passed, 0 failed, 0 skipped

Test count: [before] → [after]
SLO regressions: none | [list]
Issues opened: none | [GitHub issue numbers]
Deferred with decision record: none | [docs/decisions/ filenames]
```

---

## Eliminated Components (Never Re-introduce)

Vector database · Embedding model · Chunking / splitter logic · ETL pipeline ·
Reranker model · Document sync jobs · Semantic search index · pgvector

---

## Full Stack Reference

| Component | Tool | Version | Purpose |
|-----------|------|---------|---------|
| Node/edge store | PostgreSQL | 16 | Primary lattice, audit log |
| Graph traversal | Postgres recursive CTEs | — | No separate graph DB |
| Row-level isolation | Postgres RLS | — | Multi-tenant data separation |
| Cycle detection | `networkx` | ≥3.3 | Johnson's algorithm on subgraphs |
| Immutable snapshots | Git + local FS / S3 | — | Content-addressed source of truth |
| Policy engine | Open Policy Agent | ≥0.65 | Sidecar; pre-prompt evaluation |
| MCP tools | Custom Python scripts | — | `git show`, `grep`, `read_file_snippet` |
| Semantic router | `aurelio-ai/semantic-router` | ≥0.1 | Local; no API call |
| Query decomposer | LangGraph | ≥0.2 | Multi-intent subgraph splitter |
| Compiled context cache | Redis | 7.x | Lane A hits < 10ms |
| Compaction daemon | vLLM + 3B distilled model | ≥0.5 | Lane C; Watch Path |
| Confidence calibration | `scikit-learn` isotonic | ≥1.4 | Weekly per-domain |
| GC / decay | Celery beat + Redis | ≥5.3 | Weekly + event-triggered |
| Model proxy | LiteLLM | ≥1.35 | Unified routing + cost tracking |
| Metrics | Prometheus + fastapi-instrumentator | — | SLO monitoring |
| PDF extraction | `pdfplumber` | ≥0.11 | Lane G |
| Confluence | `atlassian-python-api` | ≥3.41 | Lane G |
| SharePoint | `msgraph-sdk` | ≥1.0 | Lane G |

---

*Version: 2.0 — Master (merged) | Architecture: Lattice-JIT Compiler v3.1*
*Sources: PLAN.md · README.md · six-round design session (conv.md) · task board v1 · engineering roadmap v1*