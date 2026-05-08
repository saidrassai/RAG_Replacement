"""GRPO reward function powered by LLM-as-a-Verifier.

Wires the fine-grained trajectory verifier into the GRPO training loop
for the finance agent model (Qwen3.5-9B).

Usage during GRPO training:
    from lattice_jit.verifier.reward import FinanceGRPOReward

    reward_fn = FinanceGRPOReward(model_provider="deepseek")  # or "gemini"

    def compute_reward(trajectory: str, task: dict) -> float:
        return reward_fn.score(task["query"], trajectory, task.get("ground_truth"))

For test-time best-of-N selection:
    candidates = agent.generate_n(query, n=3)
    best_idx, score, result = reward_fn.select_best(query, candidates)
    return candidates[best_idx]
"""

from __future__ import annotations

from typing import Any

from lattice_jit.verifier import LLMVerifier, VerificationResult, create_finance_verifier


# ═══════════════════════════════════════════════════════════════════════════════
# GRPO Reward Function
# ═══════════════════════════════════════════════════════════════════════════════


class FinanceGRPOReward:
    """GRPO reward function for finance agent training.

    Replaces discrete LLM-as-Judge scoring with continuous expected-value
    rewards from the LLM-as-a-Verifier methodology.

    Reward component weights (configurable):
        correctness: 0.45  — answer matches ground truth, numbers correct
        methodology: 0.25  — tools used in correct order with correct params
        citations:   0.15  — every fact cites source + page + table
        completeness:0.15  — all query parts answered, charts generated if requested

    Usage:
        reward_fn = FinanceGRPOReward(model_provider="deepseek")
        score = reward_fn.score(query, trajectory_text, ground_truth)
    """

    def __init__(
        self,
        *,
        model_provider: str | None = None,
        model_name: str | None = None,
        k_repeats: int = 4,
        granularity: int = 5,
        weights: dict[str, float] | None = None,
    ):
        """
        Args:
            model_provider: litellm provider (e.g. "deepseek", "gemini").
            model_name: Model name override.
            k_repeats: Repeated verifications per criterion (K).
            granularity: Score tokens (G). 5 = A-E.
            weights: Override default criterion weights.
                     Keys: "correctness", "methodology", "citations", "completeness".
        """
        self._weights = weights or {
            "correctness": 0.45,
            "methodology": 0.25,
            "citations": 0.15,
            "completeness": 0.15,
        }

        self._verifier = create_finance_verifier(
            k_repeats=k_repeats,
            granularity=granularity,
            model_provider=model_provider,
            model_name=model_name,
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def score(
        self,
        query: str,
        trajectory: str,
        ground_truth: str | None = None,
    ) -> float:
        """Compute GRPO reward for a single trajectory.

        Returns a continuous float in [0, 1], weighted by criterion importance.
        """
        result = self._verifier.evaluate(query, trajectory, ground_truth=ground_truth)
        return self._weighted_score(result)

    def score_with_breakdown(
        self,
        query: str,
        trajectory: str,
        ground_truth: str | None = None,
    ) -> tuple[float, VerificationResult]:
        """Compute reward + get full per-criterion breakdown.

        Useful for logging per-step tool accuracy during training.
        """
        result = self._verifier.evaluate(query, trajectory, ground_truth=ground_truth)
        return self._weighted_score(result), result

    def select_best(
        self,
        query: str,
        trajectories: list[str],
        ground_truth: str | None = None,
    ) -> tuple[int, float, VerificationResult]:
        """Select the best trajectory from N candidates via round-robin tournament.

        Returns (index, score, full_verification_result).
        """
        return self._verifier.round_robin_select(query, trajectories, ground_truth=ground_truth)

    def tool_scores(
        self,
        query: str,
        trajectory: str,
        ground_truth: str | None = None,
    ) -> dict[str, float]:
        """Return per-criterion scores for tool-level analysis.

        Maps directly to: SQL correctness, analysis accuracy,
        visualization fidelity, output completeness.
        """
        result = self._verifier.evaluate(query, trajectory, ground_truth=ground_truth)
        return {criterion: r.score for criterion, r in result.criteria.items()}

    # ── Private ──────────────────────────────────────────────────────────────

    def _weighted_score(self, result: VerificationResult) -> float:
        """Apply criterion weights to produce a single reward scalar."""
        total = 0.0
        for criterion, criterion_result in result.criteria.items():
            # Match criterion substrings to weight keys
            weight = 0.25  # default if no match
            for key, w in self._weights.items():
                if key.lower() in criterion.lower():
                    weight = w
                    break
            total += weight * criterion_result.score
        return total


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience: create a reward function from env vars
# ═══════════════════════════════════════════════════════════════════════════════


def create_reward_from_env() -> FinanceGRPOReward:
    """Create a FinanceGRPOReward configured from environment variables.

    Env vars:
        VERIFIER_MODEL_PROVIDER  – litellm provider (default: "deepseek")
        VERIFIER_MODEL_NAME      – model name (default: "deepseek-chat")
        VERIFIER_K_REPEATS       – repeated verifications (default: 4)
        VERIFIER_GRANULARITY     – score tokens (default: 5)
        VERIFIER_WEIGHTS         – JSON dict of criterion weights (optional)
    """
    import json
    import os

    weights = None
    if w := os.environ.get("VERIFIER_WEIGHTS"):
        weights = json.loads(w)

    return FinanceGRPOReward(
        model_provider=os.environ.get("VERIFIER_MODEL_PROVIDER"),
        model_name=os.environ.get("VERIFIER_MODEL_NAME"),
        k_repeats=int(os.environ.get("VERIFIER_K_REPEATS", "4")),
        granularity=int(os.environ.get("VERIFIER_GRANULARITY", "5")),
        weights=weights,
    )
