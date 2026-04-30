"""Verify ODA-Fin-RL-8B via HuggingFace Inference API."""

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
from lattice_jit.model_proxy import HuggingFaceModelProvider

HF_TOKEN = os.environ.get("HF_TOKEN", "")


def _make_node() -> KnowledgeNode:
    return KnowledgeNode(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        node_type=NodeType.SECTION,
        title="basel_iii.md",
        body_text="The minimum CET1 ratio is 4.5% of risk-weighted assets.",
        content_hash="test-hash",
        serving_confidence=1.0,
    )


def _make_manifest(node: KnowledgeNode) -> CompiledContextManifest:
    return CompiledContextManifest(
        tenant_id=node.tenant_id,
        query_hash="hf-test",
        policy_bundle_id=UUID(int=0),
        context_hash="hf-test-ctx",
        budget_tokens=1000,
        actual_tokens=50,
        status=CompiledContextStatus.ACTIVE,
        items=[
            CompiledContextItem(
                tenant_id=node.tenant_id,
                manifest_id=UUID(int=0),
                ordinal=0,
                node_id=node.node_id,
                role=CompiledContextRole.EVIDENCE,
                token_count=50,
                score=1.0,
                snippet=node.body_text or "",
            )
        ],
    )


@pytest.mark.skipif(not HF_TOKEN, reason="HF_TOKEN not set")
def test_huggingface_provider_generates_answer() -> None:
    """Verify ODA-Fin-RL-8B produces a coherent financial answer."""
    provider = HuggingFaceModelProvider(
        model="OpenDataArena/ODA-Fin-RL-8B",
        max_output_tokens=256,
        temperature=0.0,
    )
    node = _make_node()
    manifest = _make_manifest(node)
    policy = PolicyBundle(
        tenant_id=node.tenant_id,
        query_class="compliance",
        tool_allowlist=[],
        redaction_rules=[],
        max_tokens=1000,
        phase_b_required=False,
        human_gate_required=False,
        opa_decision_hash="hf-test",
    )

    answer = provider.generate(
        query="What is the minimum CET1 capital ratio?",
        manifest=manifest,
        nodes=[node],
        policy_bundle=policy,
    )

    assert answer is not None
    assert len(answer) > 10, f"Answer too short: {answer}"
    assert "4.5" in answer, f"Answer does not contain the CET1 ratio: {answer[:200]}"
