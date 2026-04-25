from __future__ import annotations

from uuid import uuid4

from lattice_jit.contracts import CompiledContextStatus, KnowledgeNode, NodeType, PolicyBundle
from lattice_jit.core import Settings
from lattice_jit.runtime import ContextCompiler
from lattice_jit.storage import MemoryCacheStore


def test_context_compiler_respects_budget(container) -> None:
    node = KnowledgeNode(
        tenant_id=uuid4(),
        node_type=NodeType.SECTION,
        title="auth.py",
        body_text="x" * 5000,
        content_hash="auth",
        serving_confidence=0.9,
    )
    container.repository.upsert_nodes([node])
    bundle = PolicyBundle(
        tenant_id=node.tenant_id,
        query_class="general",
        tool_allowlist=["git_local"],
        redaction_rules=[],
        max_tokens=100,
        phase_b_required=False,
        human_gate_required=False,
        opa_decision_hash="hash",
    )
    compiler = ContextCompiler(container.repository, MemoryCacheStore(), Settings(context_item_char_budget=800))

    manifest = compiler.compile(
        tenant_id=node.tenant_id,
        query="auth",
        selected_nodes=[node],
        policy_bundle=bundle,
    )

    assert manifest.status == CompiledContextStatus.ACTIVE
    assert manifest.actual_tokens <= bundle.max_tokens
    assert manifest.items[0].token_count <= bundle.max_tokens
