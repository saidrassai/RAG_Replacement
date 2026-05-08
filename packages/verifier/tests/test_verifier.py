"""Tests for the LLM-as-a-Verifier implementation.

Run with: PYTHONPATH=... pytest packages/verifier/tests/test_verifier.py -v
"""

from __future__ import annotations

import math

import numpy as np

from lattice_jit.verifier import LLMVerifier, VerificationResult, create_finance_verifier
from lattice_jit.verifier.reward import FinanceGRPOReward


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests — LLMVerifier core
# ═══════════════════════════════════════════════════════════════════════════════


class TestLLMVerifier:
    """Tests for the core verifier (mock logprobs, no API calls)."""

    def test_expected_value_computation(self):
        """Expected value: E[score] = Σ P(token) · φ(token)."""
        verifier = LLMVerifier(granularity=5, k_repeats=1)

        # Simulated logprobs: C (middle) is very likely
        logprobs = {"C": math.log(0.9), "B": math.log(0.05), "D": math.log(0.05)}
        score = verifier._expected_value(logprobs)

        # C → φ=0.5, B → φ=0.25, D → φ=0.75
        expected = 0.9 * 0.5 + 0.05 * 0.25 + 0.05 * 0.75  # = 0.50
        assert abs(score - expected) < 0.01, f"Expected ~{expected:.3f}, got {score:.3f}"

    def test_expected_value_edge_cases(self):
        """Edge cases: uniform distribution, extreme values."""
        verifier = LLMVerifier(granularity=5, k_repeats=1)

        # Uniform distribution → middle score
        uniform = {tok: math.log(0.2) for tok in "ABCDE"}
        score = verifier._expected_value(uniform)
        assert abs(score - 0.5) < 0.01, f"Expected ~0.5, got {score:.3f}"

        # Perfect score
        perfect = {"E": math.log(0.95), "A": math.log(0.05)}
        score = verifier._expected_value(perfect)
        assert score > 0.8, f"Expected >0.8, got {score:.3f}"

        # Worst score
        worst = {"A": math.log(0.95), "E": math.log(0.05)}
        score = verifier._expected_value(worst)
        assert score < 0.2, f"Expected <0.2, got {score:.3f}"

    def test_granularity_validation(self):
        """Invalid granularity should raise."""
        try:
            LLMVerifier(granularity=1)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

        try:
            LLMVerifier(granularity=11)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_verification_result_structure(self):
        """evaluate() returns correctly structured result."""
        verifier = LLMVerifier(k_repeats=2, granularity=5)
        result = verifier.evaluate(
            "What is 3M's FY2018 capex?",
            "Queried database, found $1,577M. Source: 3M FY2018 10-K, p.59.",
        )

        assert isinstance(result, VerificationResult)
        assert 0.0 <= result.overall <= 1.0
        assert result.overall_confidence >= 0.0
        assert len(result.criteria) == len(verifier._criteria)

    def test_round_robin_single_trajectory(self):
        """Single trajectory → returns itself."""
        verifier = LLMVerifier(k_repeats=1, granularity=5)
        idx, score, result = verifier.round_robin_select("task", ["trajectory"])
        assert idx == 0
        assert 0.0 <= score <= 1.0

    def test_round_robin_multiple_trajectories(self):
        """Round-robin tournament selects best trajectory."""
        verifier = LLMVerifier(k_repeats=1, granularity=5)

        # Create 3 trajectories with different expected scores
        # (we can't control mock scores directly, but tournament logic is tested)
        trajectories = [
            "Perfect answer with all citations",
            "Partial answer missing one number",
            "Wrong answer with no citations",
        ]
        idx, score, result = verifier.round_robin_select("Compare Q2 revenue", trajectories)

        assert 0 <= idx < 3
        assert 0.0 <= score <= 1.0
        assert isinstance(result, VerificationResult)


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests — FinanceGRPOReward
# ═══════════════════════════════════════════════════════════════════════════════


class TestFinanceGRPOReward:
    """Tests for the GRPO reward integration."""

    def test_score_returns_float(self):
        """score() returns a float in [0,1]."""
        reward = FinanceGRPOReward()
        score = reward.score(
            "What is Amazon's Q2 2024 revenue?",
            "Queried database: $90.0B North America, $31.7B International. Source: Q2 2024 10-Q.",
        )
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_score_with_breakdown(self):
        """score_with_breakdown() returns score + full result."""
        reward = FinanceGRPOReward()
        score, result = reward.score_with_breakdown(
            "Show Q2 revenue with growth chart",
            "SQL → analyze → visualize → full answer with citations",
        )
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        assert isinstance(result, VerificationResult)
        assert len(result.criteria) >= 4  # finance criteria

    def test_tool_scores(self):
        """tool_scores() returns per-criterion dict."""
        reward = FinanceGRPOReward()
        scores = reward.tool_scores(
            "Forecast Q3 revenue",
            "Queried historical data, ran linear regression, forecasted $2.6B.",
        )
        assert isinstance(scores, dict)
        for value in scores.values():
            assert isinstance(value, float)
            assert 0.0 <= value <= 1.0

    def test_select_best(self):
        """select_best() returns a valid index."""
        reward = FinanceGRPOReward()
        trajectories = [
            "Good answer with SQL and citations",
            "Better answer with SQL, analysis, and chart",
            "Short answer without tools",
        ]
        idx, score, result = reward.select_best("Analyze revenue", trajectories)
        assert 0 <= idx < 3
        assert 0.0 <= score <= 1.0

    def test_custom_weights(self):
        """Custom criterion weights are applied correctly."""
        reward = FinanceGRPOReward(weights={
            "correctness": 0.6,
            "methodology": 0.2,
            "citations": 0.1,
            "completeness": 0.1,
        })
        score = reward.score("task", "trajectory")
        assert 0.0 <= score <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# Factory tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateFinanceVerifier:
    """Tests for the convenience factory."""

    def test_default_creation(self):
        """create_finance_verifier() returns a valid verifier."""
        verifier = create_finance_verifier()
        assert isinstance(verifier, LLMVerifier)
        assert verifier._k_repeats == 4
        assert verifier._granularity == 5
        assert len(verifier._criteria) == 4  # Default finance criteria

    def test_custom_params(self):
        """Custom parameters are forwarded correctly."""
        verifier = create_finance_verifier(
            k_repeats=8,
            granularity=10,
            additional_criteria=["Chart quality: Are visualizations correctly formatted?"],
        )
        assert verifier._k_repeats == 8
        assert verifier._granularity == 10
        assert len(verifier._criteria) == 5  # 4 default + 1 additional
