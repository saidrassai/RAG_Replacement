from __future__ import annotations

from uuid import UUID

from lattice_jit.contracts import KnowledgeNode, NodeType
from lattice_jit.runtime.routing import SemanticRouter


def _node(title: str, body: str) -> KnowledgeNode:
    return KnowledgeNode(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        node_type=NodeType.SECTION,
        title=title,
        body_text=body,
        content_hash=f"hash-{title}",
        serving_confidence=1.0,
    )


def test_baseline_router_selects_lexical_overlap_first() -> None:
    router = SemanticRouter(mode="baseline", max_nodes=2)
    auth = _node("auth.py", "enforce auth before account read")
    billing = _node("billing.py", "invoice aggregation and tax")

    selected = router.select("where is auth enforced", [billing, auth], None)

    assert selected[0].title == "auth.py"


def test_hybrid_router_captures_semantic_similarity() -> None:
    router = SemanticRouter(mode="hybrid", max_nodes=1)
    authn = _node("security.py", "this module authenticates user sessions")
    logs = _node("logs.py", "append-only event sink")

    selected = router.select("authentication", [logs, authn], None)

    assert len(selected) == 1
    assert selected[0].title == "security.py"


def test_subgraph_ids_take_precedence_over_router_mode() -> None:
    target = _node("target.py", "target content")
    other = _node("other.py", "other content")
    router = SemanticRouter(mode="hybrid", max_nodes=2)

    selected = router.select("anything", [other, target], [target.node_id])

    assert [node.node_id for node in selected] == [target.node_id]


def test_unknown_mode_falls_back_to_baseline() -> None:
    router = SemanticRouter(mode="not-a-mode", max_nodes=1)
    auth = _node("auth.py", "auth checks")
    random = _node("random.py", "misc")

    selected = router.select("auth", [random, auth], None)

    assert selected[0].title == "auth.py"


# ── Embedding Router Tests ──────────────────────────────────────────────────


def test_hybrid_router_falls_back_to_lexical_when_embeddings_disabled() -> None:
    from lattice_jit.runtime.routing import HybridSemanticRouter

    router = HybridSemanticRouter(max_nodes=8)
    node = KnowledgeNode(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        node_type=NodeType.SECTION,
        title="capital_requirements.md",
        body_text="Basel III tier 1 capital ratio minimum requirements",
        content_hash="hash-cr",
        serving_confidence=1.0,
    )
    selected = router.select("capital adequacy rules", [node], None)
    assert len(selected) == 1


def test_cosine_similarity_identical() -> None:
    from lattice_jit.runtime.embedding import cosine_similarity

    vec = [1.0, 2.0, 3.0]
    assert cosine_similarity(vec, vec) == 1.0


def test_cosine_similarity_orthogonal() -> None:
    from lattice_jit.runtime.embedding import cosine_similarity

    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_empty_vectors() -> None:
    from lattice_jit.runtime.embedding import cosine_similarity

    assert cosine_similarity([], []) == 0.0


# ── SemanticRouter backend_kwargs forwarding ────────────────────────────────


def test_semantic_router_forwards_backend_kwargs_to_hybrid() -> None:
    from lattice_jit.runtime.routing import HybridSemanticRouter, SemanticRouter

    router = SemanticRouter(mode="hybrid", max_nodes=5)
    backend = router._backend()
    assert isinstance(backend, HybridSemanticRouter)
    assert backend.max_nodes == 5
