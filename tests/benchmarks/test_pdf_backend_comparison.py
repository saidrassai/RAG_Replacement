"""Side-by-side comparison: pdfplumber vs docling on FinanceBench.

Runs the same 4 FinanceBench questions through both backends and
compares accuracy scores.

Usage:
    DEEPSEEK_API_KEY=sk-... pytest tests/benchmarks/test_pdf_backend_comparison.py -v -s
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from lattice_jit.contracts import PhaseBMode, QueryRequest
from lattice_jit.core import build_container, get_settings

FINANCEBENCH_PATH = Path("/tmp/financebench")
QUESTIONS_FILE = FINANCEBENCH_PATH / "data" / "financebench_open_source.jsonl"
PDFS_DIR = FINANCEBENCH_PATH / "pdfs"
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


COMPARISON_QUESTIONS = [
    ("3M_2018_10K.pdf", "What is the FY2018 capital expenditure amount (in USD millions) for 3M?", "$1577.00"),
    ("AES_2022_10K.pdf", "What quantity of restructuring costs are directly outlined in AES FY2022 10-K?", "restructuring"),
    ("AMERICANEXPRESS_2022_10K.pdf", "Which debt securities are registered on a national exchange in FY2022?", "registered"),
    ("BESTBUY_2024Q2_10Q.pdf", "Was there any drop in Cash between FY 2023 and Q2 FY2024 for Best Buy?", "drop"),
]


def _run_benchmark(backend: str) -> dict:
    """Run benchmark with a specific PDF backend."""
    tenant = UUID("00000000-0000-0000-0000-00000000c0de")
    settings = get_settings()
    if DEEPSEEK_KEY:
        settings = settings.model_copy(update={
            "model_provider": "litellm",
            "litellm_model": "deepseek/deepseek-chat",
            "litellm_temperature": 0.0,
            "litellm_max_output_tokens": 1024,
        })
    settings = settings.model_copy(update={
        "database_url": f"sqlite+pysqlite:////tmp/lattice_jit_cmp_{uuid4().hex[:8]}.sqlite3",
        "redis_url": "memory://", "celery_eager": True,
        "router_mode": "hybrid", "router_max_nodes": 20,
        "max_context_tokens": 24_000, "context_item_char_budget": 12_000,
        "embedding_enabled": True, "embedding_model": "minishlab/potion-base-8M",
    })
    container = build_container(settings)
    from lattice_jit.connectors.pdf import PdfSnapshotService
    service = PdfSnapshotService(container.repository)

    results = []
    for pdf_name, question, gold_hint in COMPARISON_QUESTIONS:
        pdf_path = PDFS_DIR / pdf_name
        if not pdf_path.exists():
            continue
        if backend == "docling":
            service.ingest_docling(tenant_id=tenant, pdf_path=str(pdf_path))
        else:
            service.ingest_structured(tenant_id=tenant, pdf_path=str(pdf_path))
        response = container.query_service.run(
            QueryRequest(tenant_id=tenant, query=question, phase_b_mode=PhaseBMode.OFF)
        )
        answer = response.phase_a.answer_text.lower()
        gold_hit = gold_hint.lower() in answer
        results.append({"question": question[:80], "gold_hit": gold_hit, "answer_snippet": answer[:200]})
    return {"backend": backend, "hits": sum(1 for r in results if r["gold_hit"]), "total": len(results), "details": results}


@pytest.fixture(scope="module")
def comparison_results():
    if not QUESTIONS_FILE.exists():
        pytest.skip("FinanceBench not found at /tmp/financebench")
    if not DEEPSEEK_KEY:
        pytest.skip("DEEPSEEK_API_KEY not set")

    print("\n--- Running pdfplumber ---")
    pdfplumber_results = _run_benchmark("pdfplumber")
    print("\n--- Running docling ---")
    docling_results = _run_benchmark("docling")
    return {"pdfplumber": pdfplumber_results, "docling": docling_results}


class TestBackendComparison:
    def test_comparison_summary(self, comparison_results: dict) -> None:
        pr = comparison_results["pdfplumber"]
        dr = comparison_results["docling"]
        print("\n" + "=" * 70)
        print("PDF BACKEND COMPARISON — DeepSeek v4")
        print("=" * 70)
        print(f"{'Backend':<15} {'Gold Hits':>10} {'Total':>6} {'Rate':>8}")
        print("-" * 45)
        print(f"{'pdfplumber':<15} {pr['hits']:>10} {pr['total']:>6} {pr['hits']/pr['total']:>7.0%}")
        print(f"{'docling':<15} {dr['hits']:>10} {dr['total']:>6} {dr['hits']/dr['total']:>7.0%}")
        print("-" * 45)
        print("\nPer-question breakdown:")
        for i, (pq, dq) in enumerate(zip(pr["details"], dr["details"], strict=True)):
            print(f"  Q{i+1}: {pq['question'][:70]}")
            print(f"    pdfplumber: {'HIT' if pq['gold_hit'] else 'MISS'} | {pq['answer_snippet'][:120]}")
            print(f"    docling:    {'HIT' if dq['gold_hit'] else 'MISS'} | {dq['answer_snippet'][:120]}")
            print()
        print("=" * 70)
