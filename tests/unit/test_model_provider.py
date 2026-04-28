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
                tenant_id=node.tenant_id,
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


def test_deepseek_config_propagates_to_litellm_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_completion(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="deepseek-answer"),
                )
            ]
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=fake_completion))

    config = ModelProviderConfig(
        provider="litellm",
        litellm_model="deepseek/deepseek-chat",
        deepseek_api_key="sk-test-key",
        deepseek_base_url="https://api.deepseek.com/v1",
    )
    provider = build_model_provider(config)
    node = _node("auth.py", "auth checks happen here")
    answer = provider.generate(
        query="where is auth checked",
        manifest=_manifest(node),
        nodes=[node],
        policy_bundle=_policy_bundle(node.tenant_id),
    )

    assert answer == "deepseek-answer"
    assert calls["model"] == "deepseek/deepseek-chat"
    assert calls["api_key"] == "sk-test-key"
    assert calls["api_base"] == "https://api.deepseek.com/v1"


def test_enhanced_prompt_includes_role_and_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages_captured: list[list[dict[str, str]]] = []

    def fake_completion(**kwargs):
        messages_captured.append(kwargs["messages"])
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="enhanced-answer"),
                )
            ]
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=fake_completion))

    provider = LiteLLMModelProvider(model="test-model")
    node = _node("policy.md", "Compliance policy: customer identifiers must remain redacted.")
    answer = provider.generate(
        query="What is the compliance policy?",
        manifest=_manifest(node),
        nodes=[node],
        policy_bundle=_policy_bundle(node.tenant_id),
    )

    assert answer == "enhanced-answer"
    system_msg = messages_captured[0][0]["content"]
    assert "financial knowledge assistant" in system_msg.lower()
    assert "source=" in system_msg.lower() or "provenance" in system_msg.lower()
    user_msg = messages_captured[0][1]["content"]
    assert "EVIDENCE" in user_msg or "score=" in user_msg


def test_prompt_caching_params_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_completion(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="cached-answer"),
                )
            ]
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=fake_completion))

    provider = LiteLLMModelProvider(prompt_caching_enabled=True)
    node = _node("auth.py", "auth checks happen here")
    provider.generate(
        query="where is auth checked",
        manifest=_manifest(node),
        nodes=[node],
        policy_bundle=_policy_bundle(node.tenant_id),
    )

    assert "cache" in calls
    assert calls["cache"] == {"type": "ephemeral"}


def test_prompt_caching_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_completion(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="no-cache-answer"),
                )
            ]
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=fake_completion))

    provider = LiteLLMModelProvider()
    node = _node("auth.py", "auth checks happen here")
    provider.generate(
        query="where is auth checked",
        manifest=_manifest(node),
        nodes=[node],
        policy_bundle=_policy_bundle(node.tenant_id),
    )

    assert "cache" not in calls
