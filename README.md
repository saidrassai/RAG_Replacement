# Lattice-JIT Compiler v3.1

Python-first modular monorepo scaffold for the first vertical slice of the Lattice-JIT architecture.

## Project framing

Lattice-JIT is a CPU-first enterprise RAG runtime prototype. It focuses on policy-enforced context compilation, provenance, human review, auditability, and document ingestion rather than unsupported accuracy claims.

## Workspace

- `apps/api`: FastAPI surface
- `apps/cli`: Typer operator CLI
- `apps/worker`: Celery worker and scheduled jobs
- `packages/*`: shared contracts and domain packages
- `ops/docker`: local-first Docker assets
- `ops/opa`: policy bundle scaffold

## CPU-first document parsing

The default PDF ingestion path is `pymupdf4llm`, which produces Markdown page chunks suitable for RAG and works on CPU-only machines. `pdfplumber` remains available for table-heavy extraction, and `pypdf2` remains as the legacy fallback. Docling is intentionally optional because it pulls a heavy OCR/CV dependency chain and is not needed for normal tests.

Parser modes accepted by API/CLI `page_mode`:

- `pymupdf4llm` / `markdown` / `cpu` — default CPU Markdown parser
- `pdfplumber` / `structured` — table-preserving structured parser
- `page` / `document` — legacy `pypdf2` extraction modes
- `docling` — optional heavy backend, installed only through the PDF connector's Docling extra

## Production readiness

- Enterprise production-readiness blueprint: `docs/plans/enterprise-production-readiness-blueprint.md`

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
