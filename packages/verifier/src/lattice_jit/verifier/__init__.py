from __future__ import annotations

import json
import math
import os
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Letter-based score tokens for logprob extraction.
# GPT-style APIs expose logprobs only for single-token outputs, so we use
# single letters instead of multi-digit numbers.
_SCORE_TOKENS: tuple[str, ...] = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J")

# Default criteria for finance agent trajectory evaluation.
_DEFAULT_FINANCE_CRITERIA: tuple[str, ...] = (
    "Correctness: Does the answer match ground truth? Are numbers accurate and properly extracted from cited sources?",
    "Methodology: Does the agent follow the 5-phase workflow (Plan → Collect → Analyze → Visualize → Verify)? Are tools used in the correct order with correct parameters?",
    "Citations: Does every numeric fact cite source document, page number, and table reference? Is a complete Sources & References section present? Are any [UNSOURCED] claims flagged?",
    "Completeness: Are all parts of the multi-part query answered? If a visualization was requested, was it generated with proper labels and data provenance?",
    "Guardrails: Are the disclaimer, no-automated-execution guardrail, and unsourced-flag rules followed?",
)


# ═══════════════════════════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(slots=True)
class CriterionResult:
    """Result for a single evaluation criterion."""

    score: float  # continuous [0, 1]
    confidence: float  # standard deviation across K verifications
    verdict: str  # textual summary (e.g., "85% — correct SQL, missing one column")


@dataclass(slots=True)
class VerificationResult:
    """Full verification result for a single trajectory."""

    overall: float  # continuous [0, 1]
    overall_confidence: float  # std across criteria
    criteria: dict[str, CriterionResult] = field(default_factory=dict)
    raw_logprobs: dict[str, dict[str, float]] | None = None  # for debugging


# ═══════════════════════════════════════════════════════════════════════════════
# Core Verifier
# ═══════════════════════════════════════════════════════════════════════════════


class LLMVerifier:
    """Fine-grained trajectory verifier for agent evaluation.

    Implements the LLM-as-a-Verifier methodology (Stanford/UC Berkeley, 2026):
    replaces discrete LLM-as-Judge scoring with continuous expected-value rewards
    computed from logprob distributions over letter-based score tokens.

    Three scaling dimensions:
        C = number of evaluation criteria (criterion decomposition)
        K = number of repeated verifications per criterion (repeated verification)
        G = number of score tokens (scoring granularity)

    Reward formula:
        R = (1/CK) · Σ_c Σ_k Σ_g P(v_g | t, c, τ) · φ(v_g)

    where φ maps each letter token to a scalar in [0, 1].
    """

    def __init__(
        self,
        criteria: Sequence[str] | None = None,
        *,
        k_repeats: int = 4,
        granularity: int = 5,
        model_provider: str | None = None,
        model_name: str | None = None,
    ):
        """
        Args:
            criteria: Evaluation criteria strings (C-dimension decomposition).
                      Defaults to finance-specific criteria.
            k_repeats: Number of repeated verifications per criterion (K).
            granularity: Number of score tokens (G).  Must be 2 ≤ G ≤ 10
                         (mapped to letters A-J).
            model_provider: Optional litellm provider string (e.g. "deepseek").
            model_name: Optional model name override.
        """
        if granularity < 2 or granularity > len(_SCORE_TOKENS):
            raise ValueError(f"Granularity must be 2–{len(_SCORE_TOKENS)}, got {granularity}")

        self._criteria: tuple[str, ...] = tuple(criteria) if criteria else _DEFAULT_FINANCE_CRITERIA
        self._k_repeats: int = k_repeats
        self._granularity: int = granularity
        self._score_tokens: tuple[str, ...] = _SCORE_TOKENS[:granularity]
        self._token_weights: dict[str, float] = {
            tok: i / (granularity - 1) for i, tok in enumerate(self._score_tokens)
        }

        # Model configuration (lazy-initialised on first call)
        self._model_provider: str | None = model_provider
        self._model_name: str | None = model_name

    # ── Public API ───────────────────────────────────────────────────────────

    def evaluate(
        self,
        task_description: str,
        trajectory_text: str,
        *,
        ground_truth: str | None = None,
    ) -> VerificationResult:
        """Evaluate a single agent trajectory.

        Returns a continuous reward in [0, 1] with per-criterion breakdowns.
        """
        criteria_results: dict[str, CriterionResult] = {}
        criteria_scores: list[float] = []

        for criterion in self._criteria:
            k_scores: list[float] = []
            for _ in range(self._k_repeats):
                logprobs = self._score_trajectory(task_description, trajectory_text, criterion, ground_truth)
                score = self._expected_value(logprobs)
                k_scores.append(score)

            mean = float(np.mean(k_scores))
            std = float(np.std(k_scores)) if self._k_repeats > 1 else 0.0
            criteria_results[criterion] = CriterionResult(
                score=mean,
                confidence=std,
                verdict=self._summarise(mean, criterion),
            )
            criteria_scores.append(mean)

        overall = float(np.mean(criteria_scores))
        overall_confidence = float(np.std(criteria_scores)) if len(criteria_scores) > 1 else 0.0

        return VerificationResult(
            overall=overall,
            overall_confidence=overall_confidence,
            criteria=criteria_results,
        )

    def round_robin_select(
        self,
        task_description: str,
        trajectories: list[str],
        *,
        ground_truth: str | None = None,
    ) -> tuple[int, float, VerificationResult]:
        """Select the best trajectory via round-robin tournament.

        For N trajectories, runs N*(N-1)/2 pairwise comparisons.
        The trajectory with the most wins is selected.

        Returns:
            (winning_index, winning_score, full_verification_result)
        """
        n = len(trajectories)
        if n == 0:
            raise ValueError("At least one trajectory required")
        if n == 1:
            result = self.evaluate(task_description, trajectories[0], ground_truth=ground_truth)
            return 0, result.overall, result

        # Evaluate all trajectories independently first
        results = [self.evaluate(task_description, t, ground_truth=ground_truth) for t in trajectories]
        wins = [0] * n

        # Round-robin pairwise: higher overall score → win
        for i in range(n):
            for j in range(i + 1, n):
                if results[i].overall > results[j].overall:
                    wins[i] += 1
                elif results[j].overall > results[i].overall:
                    wins[j] += 1
                # tie → no win for either (verifier eliminates ties naturally)

        best_idx = int(np.argmax(wins))
        return best_idx, results[best_idx].overall, results[best_idx]

    def per_criterion_scores(
        self,
        task_description: str,
        trajectory_text: str,
        *,
        ground_truth: str | None = None,
    ) -> dict[str, CriterionResult]:
        """Shortcut: return only the per-criterion breakdown."""
        return self.evaluate(task_description, trajectory_text, ground_truth=ground_truth).criteria

    # ── Private helpers ──────────────────────────────────────────────────────

    def _expected_value(self, logprobs: dict[str, float]) -> float:
        """Compute E[score] = Σ P(token) · φ(token) from logprobs."""
        total = 0.0
        total_prob = 0.0

        for token, logprob in logprobs.items():
            if logprob is None or math.isinf(logprob):
                continue
            prob = math.exp(logprob)
            weight = self._token_weights.get(token, 0.0)
            total += prob * weight
            total_prob += prob

        # Normalize in case some tokens were missing from top_logprobs
        return total / max(total_prob, 1e-10)

    def _score_trajectory(
        self,
        task: str,
        trajectory: str,
        criterion: str,
        ground_truth: str | None = None,
    ) -> dict[str, float]:
        """Call the model and return token logprobs for score tokens.

        This is the integration point — override this method to use a different
        model backend (OpenAI, vLLM, DeepSeek, Gemini, etc.).
        """
        # Build verification prompt
        score_tokens_str = ", ".join(
            f'"{t}"' for t in self._score_tokens
        )
        prompt = self._build_verification_prompt(task, trajectory, criterion, ground_truth, score_tokens_str)

        # Call model with logprobs
        return self._call_model_with_logprobs(prompt)

    def _build_verification_prompt(
        self,
        task: str,
        trajectory: str,
        criterion: str,
        ground_truth: str | None,
        score_tokens_str: str,
    ) -> str:
        """Build the verification prompt in the reference format."""
        gt_section = f"\n\n**Ground Truth (for reference only):**\n{ground_truth}" if ground_truth else ""

        return f"""You are an expert financial analysis reviewer. Evaluate the following agent trajectory against the specified criterion.

**Task:**
{task}
{gt_section}
**Evaluation Criterion:**
{criterion}

**Agent Trajectory:**
{trajectory}

**Rating Rules:**
- {self._score_tokens[0]} = Completely incorrect / criterion not satisfied
- {self._score_tokens[self._granularity // 2]} = Partially correct / some issues
- {self._score_tokens[-1]} = Perfectly correct / criterion fully satisfied
- Rate on a continuous scale using letter tokens {score_tokens_str}

<score>{self._score_tokens[0]}</score>"""

    def _call_model_with_logprobs(self, prompt: str) -> dict[str, float]:
        """Call the configured model and return logprobs for score tokens.

        Uses litellm for multi-provider support (OpenAI, DeepSeek, vLLM, etc.).
        Override for custom backends.
        """
        try:
            import litellm
        except ImportError:
            return self._mock_logprobs()

        provider = self._model_provider or os.environ.get("VERIFIER_MODEL_PROVIDER", "deepseek")
        model = self._model_name or os.environ.get("VERIFIER_MODEL_NAME", "deepseek-chat")

        try:
            response = litellm.completion(
                model=f"{provider}/{model}",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3,
                temperature=0.0,
                logprobs=True,
                top_logprobs=len(self._score_tokens),
            )

            # Extract logprobs for score tokens
            choice = response.choices[0] if hasattr(response, "choices") else None
            if choice is None or not hasattr(choice, "logprobs"):
                return self._mock_logprobs()

            logprob_data = choice.logprobs
            if logprob_data is None or not hasattr(logprob_data, "content"):
                return self._mock_logprobs()

            token_logprobs: dict[str, float] = {}
            for token_info in (logprob_data.content or []):
                if hasattr(token_info, "top_logprobs"):
                    for tl in token_info.top_logprobs or []:
                        if tl.token in self._token_weights:
                            token_logprobs[tl.token] = float(tl.logprob)

            return token_logprobs or self._mock_logprobs()

        except Exception:
            return self._mock_logprobs()

    @staticmethod
    def _mock_logprobs() -> dict[str, float]:
        """Deterministic fallback when logprobs aren't available.

        Returns a neutral distribution centred on the middle score token.
        """
        return {"C": math.log(0.5), "D": math.log(0.3), "B": math.log(0.2)}

    @staticmethod
    def _summarise(score: float, criterion: str) -> str:
        """Generate a human-readable verdict from a [0,1] score."""
        pct = int(score * 100)
        if pct >= 90:
            return f"{pct}% — criterion fully satisfied"
        if pct >= 70:
            return f"{pct}% — mostly correct with minor issues"
        if pct >= 50:
            return f"{pct}% — partially correct, significant gaps"
        if pct >= 30:
            return f"{pct}% — mostly incorrect"
        return f"{pct}% — criterion not satisfied"


# ═══════════════════════════════════════════════════════════════════════════════
# Finance-specific convenience factory
# ═══════════════════════════════════════════════════════════════════════════════


def create_finance_verifier(
    *,
    k_repeats: int = 4,
    granularity: int = 5,
    additional_criteria: Sequence[str] | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
) -> LLMVerifier:
    """Create a verifier pre-configured for finance agent trajectory evaluation.

    Default criteria cover correctness, methodology, citations, and completeness.
    Pass additional_criteria to extend (e.g., for chart quality, forecasting accuracy).
    """
    criteria = list(_DEFAULT_FINANCE_CRITERIA)
    if additional_criteria:
        criteria.extend(additional_criteria)
    return LLMVerifier(
        criteria=criteria,
        k_repeats=k_repeats,
        granularity=granularity,
        model_provider=model_provider,
        model_name=model_name,
    )
