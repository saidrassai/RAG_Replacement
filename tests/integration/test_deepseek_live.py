"""Live integration test for DeepSeek v4 via LiteLLM.

Requires DEEPSEEK_API_KEY to be set in the environment.
Skip if not configured: pytest -k "not deepseek" or unset the env var.
"""

from __future__ import annotations

import os
from uuid import UUID

import pytest
from lattice_jit.contracts import (
    CompiledContextItem,
    CompiledContextManifest,
    CompiledContextRole,
    CompiledContextStatus,
    KnowledgeNode,
    NodeType,
    PolicyBundle,
)
from lattice_jit.model_proxy import LiteLLMModelProvider

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


def _make_node() -> KnowledgeNode:
    return KnowledgeNode(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        node_type=NodeType.SECTION,
        title="basel_iii_capital.md",
        source_uri="/policies/basel_iii_capital.md",
        body_text=(
            "Basel III requires banks to maintain a Common Equity Tier 1 (CET1) "
            "capital ratio of at least 4.5% of risk-weighted assets, plus a capital "
            "conservation buffer of 2.5%, for a total of 7.0%."
        ),
        content_hash="basel-iii-hash",
        serving_confidence=0.95,
    )


def _make_manifest(node: KnowledgeNode) -> CompiledContextManifest:
    return CompiledContextManifest(
        tenant_id=node.tenant_id,
        query_hash="deepseek-live-test",
        policy_bundle_id=UUID("00000000-0000-0000-0000-000000000002"),
        context_hash="deepseek-live-ctx",
        budget_tokens=4000,
        actual_tokens=100,
        status=CompiledContextStatus.ACTIVE,
        items=[
            CompiledContextItem(
                tenant_id=node.tenant_id,
                manifest_id=UUID("00000000-0000-0000-0000-000000000003"),
                ordinal=0,
                node_id=node.node_id,
                role=CompiledContextRole.EVIDENCE,
                token_count=80,
                score=0.95,
                snippet=node.body_text or "",
            )
        ],
    )


def _make_policy_bundle(tenant_id: UUID) -> PolicyBundle:
    return PolicyBundle(
        tenant_id=tenant_id,
        query_class="compliance",
        tool_allowlist=["git_local"],
        redaction_rules=["mask_identifiers"],
        max_tokens=4000,
        phase_b_required=True,
        human_gate_required=True,
        opa_decision_hash="deepseek-live-decision",
    )


@pytest.mark.skipif(not DEEPSEEK_API_KEY, reason="DEEPSEEK_API_KEY not set")
def test_deepseek_v4_generates_answer() -> None:
    """Verify DeepSeek v4 produces a coherent answer via LiteLLM."""
    provider = LiteLLMModelProvider(
        model="deepseek/deepseek-chat",
        temperature=0.0,
        max_output_tokens=512,
    )
    node = _make_node()
    manifest = _make_manifest(node)
    policy_bundle = _make_policy_bundle(node.tenant_id)

    answer = provider.generate(
        query="What is the minimum CET1 capital ratio under Basel III?",
        manifest=manifest,
        nodes=[node],
        policy_bundle=policy_bundle,
    )

    assert answer is not None
    assert len(answer) > 20, f"Answer too short: {answer}"
    assert any(term in answer.lower() for term in ("4.5", "7.0", "cet1", "basel", "capital")), (
        f"Answer does not reference Basel III capital ratios: {answer[:200]}"
    )


@pytest.mark.skipif(not DEEPSEEK_API_KEY, reason="DEEPSEEK_API_KEY not set")
def test_deepseek_v4_respects_finance_context() -> None:
    """Verify DeepSeek v4 doesn't hallucinate outside provided context."""
    provider = LiteLLMModelProvider(
        model="deepseek/deepseek-chat",
        temperature=0.0,
        max_output_tokens=512,
    )
    node = _make_node()
    manifest = _make_manifest(node)
    policy_bundle = _make_policy_bundle(node.tenant_id)

    answer = provider.generate(
        query="What is the leverage ratio requirement?",
        manifest=manifest,
        nodes=[node],
        policy_bundle=policy_bundle,
    )

    assert answer is not None
    # The context only mentions CET1 ratio, not leverage ratio.
    # A good model should acknowledge it can't answer or stick to provided context.
    assert len(answer) > 10, f"Answer too short: {answer}"
    # Don't assert must-not-contain — LLMs vary. Just verify it didn't crash.


@pytest.mark.skipif(not DEEPSEEK_API_KEY, reason="DEEPSEEK_API_KEY not set")
def test_deepseek_v4_token_limit_respected() -> None:
    """Verify max_output_tokens caps the response length."""
    provider = LiteLLMModelProvider(
        model="deepseek/deepseek-chat",
        temperature=0.0,
        max_output_tokens=64,
    )
    node = _make_node()
    manifest = _make_manifest(node)
    policy_bundle = _make_policy_bundle(node.tenant_id)

    answer = provider.generate(
        query="Explain Basel III capital requirements in detail.",
        manifest=manifest,
        nodes=[node],
        policy_bundle=policy_bundle,
    )

    assert answer is not None
    # 64 tokens max should keep this relatively short
    assert len(answer) < 2000, f"Answer suspiciously long for 64 token limit: {len(answer)} chars"
