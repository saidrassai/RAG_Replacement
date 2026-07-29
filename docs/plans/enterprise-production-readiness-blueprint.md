# Enterprise Production Readiness Blueprint

Last inspected: 2026-07-29

This document is the execution backlog for moving RAG_Replacement from a working CPU-first RAG prototype to an enterprise-grade Agentic RAG platform.

Current readiness estimate: 6/10 for production-grade readiness.

Do not claim "enterprise production-grade" until the release gates in this document pass with real measured results.

## Current State

Implemented and useful today:

- Modular monorepo with API, CLI, worker, storage, runtime, policy, governance, connectors, and verifier packages.
- Git/local, PDF, SharePoint, and Confluence ingestion surfaces.
- CPU-first PDF parser path using PyMuPDF4LLM, with pdfplumber and legacy PyPDF2 fallbacks.
- Query path: snapshot lookup, router selection, policy evaluation, context manifest compilation, answer persistence, provenance refs, and optional Phase B scheduling.
- Basic API-key middleware, per-tenant in-memory rate limiting, audit events, review queue, OPA-compatible policy adapter, Celery worker, and Docker Compose.
- Unit, integration, benchmark, and quick e2e tests. Latest broad non-Docker run: 140 passed, 7 skipped, 1 Docker boot test deselected.

Not production-grade yet:

- Auth is optional and endpoint handlers still accept user-supplied tenant IDs.
- Retrieval is in-process over snapshot nodes, not backed by persistent vector and sparse indexes.
- There is no document-level ACL model or ACL-aware retrieval filter.
- Phase B verification is still a placeholder.
- Citation correctness, faithfulness, unsupported-answer refusal, latency, cost, and retrieval quality are not enforced by CI gates.
- Docker Compose is local-first and not hardened for production secrets, TLS, migrations, observability, backups, or scaling.

## Definition Of Done For Enterprise Grade

RAG_Replacement can be called enterprise production-grade only when all of these are true:

- A user identity is bound to every request, and tenant ID cannot be spoofed from request bodies or query params.
- Retrieval applies document-level permissions before ranking, context compilation, generation, provenance, and audit export.
- Ingestion is asynchronous, resumable, idempotent, and records per-file success/failure state.
- Retrieval uses persistent hybrid indexes with metadata filters, reranking, and query/retrieval traces.
- Answer generation has structured refusal behavior and a blocking verification gate for citations and faithfulness.
- A fixed evaluation suite reports retrieval, answer quality, safety, cost, and latency metrics.
- CI fails on quality regressions, security regressions, schema drift, and broken Docker deployment.
- Production deployment has migrations, secrets management, readiness/liveness probes, structured logs, traces, metrics, dashboards, backups, and rollback steps.

## P0 Blockers

These are the next tasks before any production-grade claim.

### P0.1 Bind Identity To Tenant And Role

Observed gap:

- `auth_enabled` defaults to false.
- API handlers receive `tenant_id` directly from request bodies, query params, and forms.
- `get_tenant_id()` exists but is not consistently used by API routes.

To do:

- Add an `AuthContext` contract with `tenant_id`, `principal_id`, `roles`, `groups`, and `scopes`.
- Replace direct route-level `tenant_id` trust with an authenticated dependency.
- When auth is enabled, reject mismatches between authenticated tenant and supplied tenant.
- Add service-layer checks so CLI/API cannot bypass tenant enforcement accidentally.
- Add negative tests for cross-tenant snapshot, answer, review, audit, and export access.

Acceptance criteria:

- A request authenticated for tenant A cannot ingest, query, read answers, list audit events, or approve review items for tenant B.
- Tests prove cross-tenant leakage fails closed with 403 or 404.
- The API contract documents authenticated and local-dev modes separately.

### P0.2 Add Document-Level ACLs And Retrieval Filtering

Observed gap:

- `KnowledgeNode.metadata` can store arbitrary metadata, but there is no first-class ACL model.
- Retrieval starts from all nodes in a snapshot before role/group filtering.
- SharePoint and Confluence connectors do not capture source permissions.

To do:

- Add document ACL contracts: `allowed_principals`, `allowed_groups`, `allowed_roles`, `deny_principals`, `security_label`.
- Persist ACL fields in storage with indexed columns or normalized tables.
- Capture ACLs in enterprise connectors where available.
- Apply ACL filters before ranking, reranking, context compilation, provenance, and audit export.
- Add tests with two users in the same tenant who can see different documents.

Acceptance criteria:

- Unauthorized nodes never enter selected nodes, compiled manifests, prompts, answer provenance, or retrieval traces.
- Permission-denied evidence is not leaked through snippets, titles, source URIs, counts, or logs.

### P0.3 Replace Placeholder Phase B With Real Verification

Observed gap:

- Phase B currently appends "placeholder verification completed."
- Citation validator and LLM verifier exist but are not wired as blocking runtime gates.

To do:

- Define a `VerificationReport` contract with `faithfulness`, `citation_correctness`, `unsupported_claims`, `missing_citations`, and `decision`.
- Wire Phase B to verify every generated answer against the compiled context.
- Add deterministic citation checks before any LLM-as-verifier call.
- Make regulated queries fail closed or enter human review when verification is unavailable.
- Persist verification reports and expose them through API/CLI.

Acceptance criteria:

- Unsupported claims are detected and either removed, refused, or routed to review.
- Answers with missing citations cannot be marked final for regulated query classes.
- Tests cover pass, fail, verifier unavailable, and human-review paths.

### P0.4 Build A Fixed Evaluation Harness

Observed gap:

- Benchmark tests exist, but live FinanceBench and DeepSeek tests skip without local data/API keys.
- No CI quality gate checks retrieval recall, MRR, citation correctness, faithfulness, unsupported-answer rejection, cost, or latency.

To do:

- Create `evals/` with fixed datasets, expected answers, evidence IDs, and no-answer questions.
- Store evaluation outputs under `reports/evals/` or another documented artifact path.
- Add retrieval metrics: Recall@5, MRR, context precision, context recall.
- Add answer metrics: faithfulness, citation correctness, answer relevance, unsupported-answer rejection.
- Add operational metrics: P50/P95 latency, token usage, estimated cost, cache hit rate.
- Add a CI gate with configurable thresholds.

Acceptance criteria:

- `uv run --all-packages pytest tests/benchmarks` is not the only evaluation path.
- A single command produces a versioned evaluation report.
- CI fails if metrics drop beyond configured thresholds.
- Resume/project claims use only measured numbers from committed reports.

### P0.5 Prove Docker Stack Boot End To End

Observed gap:

- Compose config test passes, but the full Docker stack boot test was not part of the latest clean run.
- Compose uses local default credentials and stub model.

To do:

- Make `test_docker_compose_boots_local_stack` reliable and bounded.
- Add a migration step before API/worker start.
- Add production-like env examples with non-default credentials and auth enabled.
- Document how to run the full stack test and how long it should take.

Acceptance criteria:

- Full e2e Docker test passes reliably on a clean machine.
- API, worker, Postgres, Redis, and OPA health checks all pass.
- The stack ingests, queries, writes provenance, writes audit events, queues review, and shuts down cleanly.

## P1 Retrieval And Agentic RAG Architecture

### P1.1 Persistent Hybrid Indexes

Observed gap:

- Router ranks Python objects returned by `list_snapshot_nodes()`.
- There is no persistent vector index, BM25 index, or retrieval table.

To do:

- Add a retrieval index abstraction with implementations for local CPU and production.
- Local CPU option: SQLite/Postgres metadata plus lightweight embeddings.
- Production option: PostgreSQL + pgvector or Qdrant for dense search, OpenSearch for BM25.
- Store embeddings and sparse index IDs with snapshot/version linkage.
- Add metadata filters for tenant, snapshot, document type, date, source, ACL, and security label.

Acceptance criteria:

- Retrieval does not require loading every snapshot node into memory.
- Recall@5 and MRR are measured before and after hybrid search.
- Index rebuild and incremental update paths are tested.

### P1.2 Reranking And Query Decomposition

Observed gap:

- `_llm_rerank_sections()`, `_is_metrics_question()`, and `_decompose_metrics_query()` exist but are not wired into `QueryService`.
- Query expansion utilities in `financial_schema.py` are not wired into routing.

To do:

- Add an explicit query planning step: classify, decompose, expand, retrieve, rerank, compile.
- Wire CPU-safe reranking first, then optional LLM/cross-encoder reranking behind settings.
- Persist decomposition and reranking traces.
- Add tests proving complex questions retrieve evidence for every sub-question.

Acceptance criteria:

- Multi-hop questions produce separate retrieval traces per sub-question.
- Reranking improves at least one measured metric without unacceptable latency or cost increase.

### P1.3 Retrieval Traceability

Observed gap:

- Compiled manifests persist selected context, but not full retrieval candidates, scores, filters, and rejected items.

To do:

- Add `retrieval_runs` and `retrieval_candidates` persistence.
- Record query normalization, planner output, filters, retriever scores, reranker scores, selected/rejected reason, latency, and index version.
- Expose traces via API/CLI for debugging and demo screenshots.

Acceptance criteria:

- Every answer can be traced from query to candidates to final cited context.
- Failed eval examples include retrieval traces automatically.

## P2 Ingestion And Document Intelligence

### P2.1 Resumable, Idempotent Ingestion

Observed gap:

- Connectors create pending snapshots, but most ingestion work is synchronous through API/CLI.
- Per-file processing state is not persisted.

To do:

- Add ingestion job and file state tables.
- Store content hash, parser version, chunker version, source version, status, error, retry count, and timestamps.
- Make ingestion idempotent by source object ID and content hash.
- Add cancellation and resume commands.

Acceptance criteria:

- A failed ingestion can resume without duplicating nodes.
- Deleted and changed source files are reflected in indexes and snapshots.

### P2.2 Enterprise Document Parsing Pipeline

Observed gap:

- PDF, DOCX, XLSX, PPTX, HTML/Confluence, and text extraction exist in separate connector paths.
- There is no unified parser contract, confidence score, table schema, OCR policy, or human-review handoff for low-confidence parsing.

To do:

- Introduce a parser interface returning Markdown, tables, figures, metadata, confidence, and provenance spans.
- Add file size and MIME validation.
- Add CPU OCR policy for scanned PDFs as an optional path.
- Normalize table extraction across PDF/XLSX/DOCX.
- Route low-confidence parses to review.

Acceptance criteria:

- Parser output has stable Markdown/JSON snapshots for regression tests.
- Table-heavy test documents preserve key values and source spans.

## P3 Generation, Safety, And Human Review

### P3.1 Structured Answer Contract

Observed gap:

- Model providers return plain text.
- Refusal, citations, calculations, and confidence are not schema-enforced.

To do:

- Require structured output: `answer`, `citations`, `calculations`, `unsupported_claims`, `confidence`, `refusal_reason`.
- Add schema validation and retry-on-invalid behavior.
- Persist structured answer fields separately from display text.

Acceptance criteria:

- Invalid model output is rejected or retried.
- No-answer questions produce a clear refusal with supporting retrieval trace.

### P3.2 Human Approval Gates

Observed gap:

- Review queue exists, but review approval does not gate answer release or tool execution.

To do:

- Add answer states: provisional, blocked_for_review, approved, rejected, final.
- Enforce human approval before finalizing regulated/high-risk answers.
- Add reviewer identity to audit events.
- Add review comments and decision reason fields.

Acceptance criteria:

- Compliance/security answers cannot become final without required gate passing.
- Audit trail shows who approved what, when, and based on which evidence.

## P4 Security And Compliance

### P4.1 Threat Model And Prompt Injection Defense

To do:

- Add a threat model document covering data exfiltration, cross-tenant leakage, prompt injection, malicious files, SSRF, path traversal, and tool abuse.
- Treat retrieved documents as untrusted content in system prompts.
- Add prompt-injection tests where source documents attempt to override instructions.
- Add allowlisted source paths and connector URL validation.

Acceptance criteria:

- Prompt injection test cases do not leak secrets, ignore ACLs, change policies, or execute tools.
- Local file ingestion cannot read outside configured allowlisted roots.

### P4.2 Secrets And Key Management

To do:

- Move connector and model credentials out of direct API form inputs.
- Add named connection records with secret references.
- Support environment, Vault-compatible, or cloud secret manager backends.
- Add key rotation documentation.

Acceptance criteria:

- Secrets are never stored in audit payloads, retrieval traces, answer text, or review queue records.
- Connectors can run from stored connection IDs.

## P5 Observability And Operations

### P5.1 Metrics, Traces, And Dashboards

Observed gap:

- Logging is basic `logging.basicConfig`.
- There is no OpenTelemetry, Prometheus, or Grafana instrumentation.

To do:

- Add structured JSON logs with request ID, tenant ID, answer ID, manifest ID, and task ID.
- Add OpenTelemetry traces around ingestion, retrieval, compilation, generation, verification, and review.
- Add Prometheus metrics for latency, errors, tokens, cost, cache hits, retrieval size, verification failures, and queue depth.
- Add Grafana dashboards and alert examples.

Acceptance criteria:

- A demo query has one trace spanning API, retrieval, model call, storage, and review queue.
- Dashboards show P95 latency, error rate, queue depth, cost, and quality-gate failure counts.

### P5.2 Reliability And Scale

To do:

- Add idempotency keys to write endpoints.
- Add pagination and limits for snapshot nodes, audit exports, review queue, and traces.
- Add database indexes for tenant/time/status fields.
- Add load tests for concurrent queries and ingestion.
- Add DLQ replay tooling and runbook.

Acceptance criteria:

- Load test report includes throughput, P95 latency, error rate, and resource usage.
- Operators can inspect and replay failed jobs safely.

## P6 Deployment Hardening

To do:

- Add Alembic migrations and stop relying on `create_all()` for production.
- Add non-root container hardening, pinned image digests, vulnerability scan, and SBOM generation.
- Add Kubernetes or production Compose manifests with TLS termination, secrets, readiness probes, resource limits, and persistent volumes.
- Add backup/restore procedure for Postgres and index stores.
- Add rollback strategy for app version, schema version, and index version.
- Add GitHub Actions CI for lint, type check, tests, Docker build, security scan, and eval gates.

Acceptance criteria:

- A clean production-like environment can deploy, migrate, serve, rollback, and restore from backup using documented commands.

## P7 Portfolio And Resume Proof

To do:

- Add an architecture diagram showing ingestion, indexes, policy, retrieval, generation, verification, review, observability, and deployment.
- Add sample datasets or generation scripts that do not require private data.
- Add API documentation screenshots or generated OpenAPI docs.
- Add demo screenshots/video for ingest, query, trace, review, and eval report.
- Add `reports/production-readiness/` with measured results.
- Add limitations and roadmap to README.

Acceptance criteria:

- Resume bullets cite real measured numbers only.
- The repo can be reviewed by a recruiter or engineer without needing private systems.

## Suggested Implementation Order

1. P0.1 identity and tenant binding.
2. P0.2 document ACL model and ACL-aware retrieval tests.
3. P0.3 real Phase B verification gate.
4. P0.4 fixed eval harness and reports.
5. P0.5 reliable full Docker e2e.
6. P1.1 persistent hybrid indexes.
7. P1.2 query decomposition and reranking.
8. P1.3 retrieval traces.
9. P2 ingestion state and unified parser contract.
10. P5 observability.
11. P6 deployment hardening.
12. P7 portfolio packaging.

## Claims Allowed Today

Safe claims:

- CPU-first enterprise RAG runtime prototype.
- Modular FastAPI/Celery/Postgres/Redis RAG architecture.
- Provenance-aware context manifests and answer events.
- Basic governance queue, audit trail, policy adapter, and connector scaffolding.
- Local benchmark and test scaffolding.

Claims not yet allowed:

- Production-grade enterprise RAG.
- Fully secure RBAC or document-level permissions.
- Hallucination-free answers.
- Proven FinanceBench accuracy.
- Proven production observability.
- Proven deployment scalability.

