"""Finance accuracy benchmark for Lattice-JIT Compiler.

Ingests curated financial documents with ground-truth facts and measures
retrieval accuracy, answer fidelity, and hallucination rate.

Usage:
    DEEPSEEK_API_KEY=sk-... pytest tests/benchmarks/test_finance_benchmark.py -v
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from lattice_jit.contracts import PhaseBMode, QueryRequest, SnapshotGitRequest
from lattice_jit.core import build_container, get_settings

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "finance"
BENCHMARK_TENANT = UUID("00000000-0000-0000-0000-00000000beef")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


# ── Benchmark Question Definition ───────────────────────────────────────────


@dataclass
class FinanceQuestion:
    question: str
    ground_truth_facts: list[str]  # Required facts the answer MUST contain
    forbidden_claims: list[str] = field(default_factory=list)  # Facts NOT in context
    source_doc_keywords: list[str] = field(default_factory=list)  # For retrieval scoring
    tolerance: float = 0.0  # Tolerance for numeric answers (e.g., 0.1 = 10%)


BASEL_III_QUESTIONS: list[FinanceQuestion] = [
    FinanceQuestion(
        question="What is the minimum Common Equity Tier 1 capital ratio under Basel III?",
        ground_truth_facts=["4.5%"],
        forbidden_claims=[],
        source_doc_keywords=["basel_iii"],
    ),
    FinanceQuestion(
        question="What is the capital conservation buffer percentage and what is the effective total CET1 requirement?",
        ground_truth_facts=["2.5%", "7.0%"],
        forbidden_claims=[],
        source_doc_keywords=["basel_iii"],
    ),
    FinanceQuestion(
        question="What is the minimum Total Capital ratio required by Basel III?",
        ground_truth_facts=["8.0%"],
        forbidden_claims=[],
        source_doc_keywords=["basel_iii"],
    ),
    FinanceQuestion(
        question="What is the Basel III leverage ratio minimum requirement?",
        ground_truth_facts=["3.0%"],
        forbidden_claims=[],
        source_doc_keywords=["basel_iii"],
    ),
    FinanceQuestion(
        question="What is the G-SIB surcharge range and how many buckets are there?",
        ground_truth_facts=["1.0%", "3.5%", "5"],
        forbidden_claims=[],
        source_doc_keywords=["basel_iii"],
    ),
    FinanceQuestion(
        question="How long is the LCR stress period and what is the minimum LCR requirement?",
        ground_truth_facts=["30-day", "100%"],
        forbidden_claims=[],
        source_doc_keywords=["basel_iii"],
    ),
    FinanceQuestion(
        question="By what date must the Basel III output floor of 72.5% be fully phased in?",
        ground_truth_facts=["January 1, 2027", "2027"],
        forbidden_claims=[],
        source_doc_keywords=["basel_iii"],
    ),
    FinanceQuestion(
        question="What is the maximum large exposure limit to a single counterparty under Basel III?",
        ground_truth_facts=["25%"],
        forbidden_claims=[],
        source_doc_keywords=["basel_iii"],
    ),
]

SEC_10K_QUESTIONS: list[FinanceQuestion] = [
    FinanceQuestion(
        question="What was ACME Financial's total revenue for fiscal year 2025?",
        ground_truth_facts=["$112.4", "112.4 billion"],
        forbidden_claims=[],
        source_doc_keywords=["acme", "10-k"],
    ),
    FinanceQuestion(
        question="What was ACME's net income for FY 2025 and how much did it increase from FY 2024?",
        ground_truth_facts=["$23.1", "billion"],
        forbidden_claims=[],
        source_doc_keywords=["acme", "10-k"],
    ),
    FinanceQuestion(
        question="How many retail branches does ACME operate and in how many states?",
        ground_truth_facts=["4,217", "50"],
        forbidden_claims=[],
        source_doc_keywords=["acme", "10-k"],
    ),
    FinanceQuestion(
        question="What was ACME's CET1 ratio at year-end 2025?",
        ground_truth_facts=["12.4%"],
        forbidden_claims=[],
        source_doc_keywords=["acme", "10-k"],
    ),
    FinanceQuestion(
        question="How much did ACME return to shareholders in FY 2025 through dividends and buybacks?",
        ground_truth_facts=["$18.2", "billion", "$7.8", "billion", "$10.4", "billion"],
        forbidden_claims=[],
        source_doc_keywords=["acme", "10-k"],
    ),
    FinanceQuestion(
        question="What is ACME's total asset size and how many employees does it have?",
        ground_truth_facts=["$847.3", "billion", "218,000"],
        forbidden_claims=[],
        source_doc_keywords=["acme", "10-k"],
    ),
    FinanceQuestion(
        question="What was the average daily VaR for ACME's trading portfolio in FY 2025?",
        ground_truth_facts=["$34.7", "million"],
        forbidden_claims=[],
        source_doc_keywords=["acme", "10-k"],
    ),
    FinanceQuestion(
        question="What is ACME's net-zero target year and sustainable finance portfolio value?",
        ground_truth_facts=["2050", "$127.3", "billion", "30%", "2030"],
        forbidden_claims=[],
        source_doc_keywords=["acme", "10-k"],
    ),
]

COMPLIANCE_QUESTIONS: list[FinanceQuestion] = [
    FinanceQuestion(
        question="What is the minimum password length required by the financial data access policy?",
        ground_truth_facts=["14", "characters"],
        forbidden_claims=[],
        source_doc_keywords=["compliance", "soc2"],
    ),
    FinanceQuestion(
        question="How long must transaction records be retained according to the data retention policy?",
        ground_truth_facts=["7 years"],
        forbidden_claims=[],
        source_doc_keywords=["compliance", "soc2"],
    ),
    FinanceQuestion(
        question="How long are audit logs required to be retained?",
        ground_truth_facts=["10 years"],
        forbidden_claims=[],
        source_doc_keywords=["compliance", "soc2"],
    ),
    FinanceQuestion(
        question="Within how many hours must a GDPR personal data breach be reported?",
        ground_truth_facts=["72", "hours"],
        forbidden_claims=[],
        source_doc_keywords=["compliance", "soc2"],
    ),
    FinanceQuestion(
        question="What is the maximum account lockout duration and after how many failed attempts?",
        ground_truth_facts=["30 minutes", "5"],
        forbidden_claims=[],
        source_doc_keywords=["compliance", "soc2"],
    ),
    FinanceQuestion(
        question="What is the maximum criminal penalty for willful violations of SEC Rule 17a-4?",
        ground_truth_facts=["20 years", "$25,000,000"],
        forbidden_claims=[],
        source_doc_keywords=["compliance", "soc2"],
    ),
    FinanceQuestion(
        question="Within how many business days must a material cybersecurity incident be reported to the SEC?",
        ground_truth_facts=["4", "business days"],
        forbidden_claims=[],
        source_doc_keywords=["compliance", "soc2"],
    ),
    FinanceQuestion(
        question="How many levels of management approval are required for privileged access?",
        ground_truth_facts=["2"],
        forbidden_claims=[],
        source_doc_keywords=["compliance", "soc2"],
    ),
]

HALLUCINATION_QUESTIONS: list[FinanceQuestion] = [
    FinanceQuestion(
        question="What is the minimum CET1 ratio under Basel IV?",
        ground_truth_facts=[],  # No facts expected — Basel IV doesn't exist in context
        forbidden_claims=["Basel IV"],  # Should not claim Basel IV exists
        source_doc_keywords=["basel_iii"],
    ),
    FinanceQuestion(
        question="What was ACME's revenue for fiscal year 2026?",
        ground_truth_facts=[],  # The document only covers through FY 2025
        forbidden_claims=["2026"],  # Should not fabricate forward-looking data
        source_doc_keywords=["acme"],
    ),
    FinanceQuestion(
        question="What is the minimum password length under GDPR Article 32?",
        ground_truth_facts=[],  # GDPR doesn't specify password length in the policy
        forbidden_claims=["GDPR Article 32"],  # The policy doesn't specify this
        source_doc_keywords=["compliance"],
    ),
]


# ── Scoring Functions ────────────────────────────────────────────────────────


def score_retrieval(answer_text: str, question: FinanceQuestion) -> float:
    """Check if the answer references the correct source document."""
    hits = sum(
        1 for kw in question.source_doc_keywords if kw.lower() in answer_text.lower()
    )
    return min(1.0, hits / max(1, len(question.source_doc_keywords)))


def score_fidelity(answer_text: str, question: FinanceQuestion) -> float:
    """Check how many required facts appear in the answer."""
    if not question.ground_truth_facts:
        return 0.5  # For no-answer-expected questions
    hits = sum(
        1 for fact in question.ground_truth_facts if fact.lower() in answer_text.lower()
    )
    return hits / len(question.ground_truth_facts)


def score_hallucination(answer_text: str, question: FinanceQuestion) -> float:
    """Check for forbidden claims. Returns 1.0 if clean, 0.0 if hallucinated.

    Honest 'not found' answers that mention forbidden terms while
    stating they are absent are not penalized.
    """
    if not question.forbidden_claims:
        return 1.0

    answer_lower = answer_text.lower()
    denial_markers = (
        "not available", "cannot find", "not contain", "no information",
        "does not contain", "not in the", "not provided", "not found",
        "not mentioned", "no mention", "not specified", "not disclosed",
        "not exist", "does not exist", "no data", "not include",
        "without", "is not",
    )
    is_denial = any(marker in answer_lower for marker in denial_markers)

    violations = 0
    for claim in question.forbidden_claims:
        if claim.lower() in answer_lower:
            violations += 1

    # If the answer is clearly stating the forbidden info is NOT present,
    # don't penalize — the model is being honest
    if is_denial and violations > 0:
        return 1.0

    return 0.0 if violations > 0 else 1.0


def score_precision(answer_text: str, question: FinanceQuestion) -> float:
    """Bonus: check for precise numeric values rather than approximations."""
    if not question.ground_truth_facts:
        return 0.5
    numeric_facts = [f for f in question.ground_truth_facts if re.search(r"\d", f)]
    if not numeric_facts:
        return 1.0
    precise_hits = sum(
        1 for fact in numeric_facts
        if re.search(re.escape(fact), answer_text, re.IGNORECASE)
    )
    return precise_hits / len(numeric_facts)


def composite_score(
    answer_text: str, question: FinanceQuestion, retrieval: float
) -> dict[str, float]:
    fidelity = score_fidelity(answer_text, question)
    hallucination = score_hallucination(answer_text, question)
    precision = score_precision(answer_text, question)
    composite = 0.15 * retrieval + 0.45 * fidelity + 0.25 * hallucination + 0.15 * precision
    return {
        "retrieval": retrieval,
        "fidelity": fidelity,
        "hallucination": hallucination,
        "precision": precision,
        "composite": composite,
    }


# ── Benchmark Runner ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def benchmark_container():
    """Build container, ingest benchmark documents, return container + snapshot_id."""
    settings = get_settings()
    # Use DeepSeek if key available, else stub
    if DEEPSEEK_KEY:
        settings = settings.model_copy(update={
            "model_provider": "litellm",
            "litellm_model": "deepseek/deepseek-chat",
            "litellm_temperature": 0.0,
            "litellm_max_output_tokens": 1024,
        })
    settings = settings.model_copy(update={
        "database_url": f"sqlite+pysqlite:////tmp/lattice_jit_bench_{uuid4().hex[:8]}.sqlite3",
        "redis_url": "memory://",
        "celery_eager": True,
        "router_mode": "hybrid",
        "router_max_nodes": 20,
        "max_context_tokens": 24_000,
        "context_item_char_budget": 12_000,
        "embedding_enabled": True,
        "embedding_model": "minishlab/potion-base-8M",
    })
    container = build_container(settings)

    # Ingest benchmark documents
    response = container.snapshot_service.ingest(
        SnapshotGitRequest(
            tenant_id=BENCHMARK_TENANT,
            repo_path=str(FIXTURES),
            include_globs=["*.md"],
        )
    )
    assert response.status.value == "completed", f"Ingestion failed: {response}"

    yield container

    # Cleanup
    import os as _os
    db_path = settings.database_url.replace("sqlite+pysqlite:///", "")
    if _os.path.exists(db_path):
        _os.remove(db_path)


@pytest.fixture
def run_query(benchmark_container):
    """Factory fixture: returns a function that runs a query and returns the answer."""
    def _run(question_text: str) -> str:
        response = benchmark_container.query_service.run(
            QueryRequest(
                tenant_id=BENCHMARK_TENANT,
                query=question_text,
                phase_b_mode=PhaseBMode.OFF,
            )
        )
        text: str = response.phase_a.answer_text
        return text
    return _run


# ── Basel III Tests ──────────────────────────────────────────────────────────


class TestBaselIII:
    @pytest.mark.parametrize("q", BASEL_III_QUESTIONS, ids=[q.question[:60] for q in BASEL_III_QUESTIONS])
    def test_basel_iii_accuracy(self, run_query, q: FinanceQuestion) -> None:
        answer = run_query(q.question)
        scores = composite_score(answer, q, score_retrieval(answer, q))
        assert scores["composite"] >= 0.30, (
            f"Score too low for: {q.question}\nAnswer: {answer[:300]}\nScores: {scores}"
        )


# ── SEC 10-K Tests ───────────────────────────────────────────────────────────


class TestSEC10K:
    @pytest.mark.parametrize("q", SEC_10K_QUESTIONS, ids=[q.question[:60] for q in SEC_10K_QUESTIONS])
    def test_sec_10k_accuracy(self, run_query, q: FinanceQuestion) -> None:
        answer = run_query(q.question)
        scores = composite_score(answer, q, score_retrieval(answer, q))
        assert scores["composite"] >= 0.30, (
            f"Score too low for: {q.question}\nAnswer: {answer[:300]}\nScores: {scores}"
        )


# ── Compliance Tests ─────────────────────────────────────────────────────────


class TestCompliance:
    @pytest.mark.parametrize("q", COMPLIANCE_QUESTIONS, ids=[q.question[:60] for q in COMPLIANCE_QUESTIONS])
    def test_compliance_accuracy(self, run_query, q: FinanceQuestion) -> None:
        answer = run_query(q.question)
        scores = composite_score(answer, q, score_retrieval(answer, q))
        assert scores["composite"] >= 0.30, (
            f"Score too low for: {q.question}\nAnswer: {answer[:300]}\nScores: {scores}"
        )


# ── Hallucination Tests ──────────────────────────────────────────────────────


class TestHallucination:
    @pytest.mark.parametrize("q", HALLUCINATION_QUESTIONS, ids=[q.question[:60] for q in HALLUCINATION_QUESTIONS])
    def test_no_hallucination(self, run_query, q: FinanceQuestion) -> None:
        answer = run_query(q.question)
        scores = composite_score(answer, q, score_retrieval(answer, q))
        assert scores["hallucination"] >= 0.5, (
            f"Hallucination detected for: {q.question}\nAnswer: {answer[:300]}\nScores: {scores}"
        )


# ── Summary Report ───────────────────────────────────────────────────────────


def test_benchmark_summary_report(run_query) -> None:
    """Generate a comprehensive benchmark summary. Always passes, prints results."""
    all_questions = BASEL_III_QUESTIONS + SEC_10K_QUESTIONS + COMPLIANCE_QUESTIONS + HALLUCINATION_QUESTIONS
    results: list[dict] = []

    for q in all_questions:
        answer = run_query(q.question)
        retrieval = score_retrieval(answer, q)
        scores = composite_score(answer, q, retrieval)
        results.append({
            "question": q.question[:80],
            **scores,
        })

    total = len(results)
    avg_composite = sum(r["composite"] for r in results) / total
    avg_fidelity = sum(r["fidelity"] for r in results) / total
    avg_hallucination = sum(r["hallucination"] for r in results) / total
    avg_retrieval = sum(r["retrieval"] for r in results) / total
    avg_precision = sum(r["precision"] for r in results) / total

    fact_questions = [r for r in results if r["fidelity"] != 0.5]
    perfect_fidelity = sum(1 for r in fact_questions if r["fidelity"] >= 1.0)
    zero_hallucination = sum(1 for r in results if r["hallucination"] >= 1.0)

    print("\n" + "=" * 70)
    print("FINANCE BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Questions tested:        {total}")
    print(f"Questions with facts:    {len(fact_questions)}")
    print(f"Hallucination checks:    {len(HALLUCINATION_QUESTIONS)}")
    print(f"Provider:                {'DeepSeek v4' if DEEPSEEK_KEY else 'Stub (deterministic)'}")
    print("-" * 70)
    print(f"Avg Retrieval Score:     {avg_retrieval:.2%}")
    print(f"Avg Fidelity Score:      {avg_fidelity:.2%}")
    print(f"Avg Hallucination Score: {avg_hallucination:.2%}")
    print(f"Avg Precision Score:     {avg_precision:.2%}")
    print(f"Avg Composite Score:     {avg_composite:.2%}")
    print(f"Perfect Fidelity:        {perfect_fidelity}/{len(fact_questions)}")
    print(f"Zero Hallucination:      {zero_hallucination}/{len(results)}")
    print("-" * 70)

    # Detailed per-question results
    for r in results:
        bar = "=" * int(r["composite"] * 20)
        print(f"  [{r['composite']:.0%}] {bar} {r['question']}")

    print("=" * 70)

    # Only fail if hallucination score is critically low
    assert avg_hallucination >= 0.5, (
        f"Hallucination rate too high: {avg_hallucination:.0%}. "
        f"System must not fabricate facts outside provided context."
    )
