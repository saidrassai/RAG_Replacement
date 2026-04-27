from __future__ import annotations

import sys
from types import SimpleNamespace
from uuid import UUID, uuid4

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
from lattice_jit.model_proxy import LiteLLMModelProvider, ModelProviderConfig, StubModelProvider, build_model_provider


def _node(title: str, body: str) -> KnowledgeNode:
    return KnowledgeNode(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        node_type=NodeType.SECTION,
        title=title,
        body_text=body,
        content_hash=f"hash-{title}",
        serving_confidence=1.0,
    )


def _manifest(node: KnowledgeNode) -> CompiledContextManifest:
    manifest_id = uuid4()
    return CompiledContextManifest(
        tenant_id=node.tenant_id,
        query_hash="query-hash",
        policy_bundle_id=uuid4(),
        context_hash="context-hash",
        budget_tokens=1000,
        actual_tokens=20,
        status=CompiledContextStatus.ACTIVE,
        items=[
            CompiledContextItem(
                manifest_id=manifest_id,
                ordinal=0,
                node_id=node.node_id,
                role=CompiledContextRole.EVIDENCE,
                token_count=20,
                score=1.0,
                snippet=node.body_text or "",
            )
        ],
    )


def _policy_bundle(tenant_id: UUID) -> PolicyBundle:
    return PolicyBundle(
        tenant_id=tenant_id,
        query_class="normal",
        tool_allowlist=[],
        redaction_rules=[],
        max_tokens=1000,
        phase_b_required=False,
        human_gate_required=False,
        opa_decision_hash="decision",
    )


def test_model_provider_factory_defaults_to_stub() -> None:
    provider = build_model_provider(ModelProviderConfig())

    assert isinstance(provider, StubModelProvider)


def test_model_provider_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown model provider"):
        build_model_provider(ModelProviderConfig(provider="unknown"))


def test_litellm_provider_uses_same_generate_interface_with_config(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_completion(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="litellm-answer"),
                )
            ]
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=fake_completion))

    provider = LiteLLMModelProvider(model="test-model", temperature=0.2, max_output_tokens=256)
    node = _node("auth.py", "auth checks happen here")
    answer = provider.generate(
        query="where is auth checked",
        manifest=_manifest(node),
        nodes=[node],
        policy_bundle=_policy_bundle(node.tenant_id),
    )

    assert answer == "litellm-answer"
    assert calls["model"] == "test-model"
    assert calls["temperature"] == 0.2
    assert calls["max_tokens"] == 256
    assert isinstance(calls["messages"], list)
