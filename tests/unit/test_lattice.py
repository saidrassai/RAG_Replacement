from __future__ import annotations

from uuid import uuid4

from lattice_jit.contracts import EdgeType, KnowledgeEdge, KnowledgeNode, NodeType
from lattice_jit.lattice import compute_confidence_band, compute_dirty_propagation, resolve_cycles


def test_resolve_cycles_breaks_lowest_confidence_edge() -> None:
    first = uuid4()
    second = uuid4()
    third = uuid4()
    edges = [
        KnowledgeEdge(tenant_id=uuid4(), from_node_id=first, to_node_id=second, edge_type=EdgeType.DEPENDS_ON),
        KnowledgeEdge(tenant_id=uuid4(), from_node_id=second, to_node_id=third, edge_type=EdgeType.DEPENDS_ON),
        KnowledgeEdge(
            tenant_id=uuid4(),
            from_node_id=third,
            to_node_id=first,
            edge_type=EdgeType.DEPENDS_ON,
            serving_confidence=0.2,
        ),
    ]

    resolved = resolve_cycles(edges)

    inactive = [edge for edge in resolved if not edge.active]
    assert len(inactive) == 1
    assert inactive[0].cycle_break_reason == "lowest_trust_edge"


def test_dirty_propagation_walks_dependents() -> None:
    first = uuid4()
    second = uuid4()
    third = uuid4()
    edges = [
        KnowledgeEdge(tenant_id=uuid4(), from_node_id=first, to_node_id=second, edge_type=EdgeType.DEPENDS_ON),
        KnowledgeEdge(tenant_id=uuid4(), from_node_id=second, to_node_id=third, edge_type=EdgeType.DERIVES_FROM),
    ]

    impacted = compute_dirty_propagation(first, edges)

    assert impacted == {first, second, third}


def test_confidence_band_uses_lowest_serving_confidence() -> None:
    nodes = [
        KnowledgeNode(
            tenant_id=uuid4(),
            node_type=NodeType.SECTION,
            title="a",
            content_hash="a",
            serving_confidence=0.9,
        ),
        KnowledgeNode(
            tenant_id=uuid4(),
            node_type=NodeType.SECTION,
            title="b",
            content_hash="b",
            serving_confidence=0.55,
        ),
    ]

    assert compute_confidence_band(nodes).value == "low"
