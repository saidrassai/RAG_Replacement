from __future__ import annotations

from collections import defaultdict, deque
from uuid import UUID

from lattice_jit.contracts import EdgeType, KnowledgeEdge


def compute_dirty_propagation(changed_node_id: UUID, edges: list[KnowledgeEdge]) -> set[UUID]:
    dependents: dict[UUID, set[UUID]] = defaultdict(set)
    for edge in edges:
        if edge.edge_type in {EdgeType.DEPENDS_ON, EdgeType.DERIVES_FROM, EdgeType.BELONGS_TO} and edge.active:
            dependents[edge.from_node_id].add(edge.to_node_id)

    impacted = {changed_node_id}
    queue = deque([changed_node_id])
    while queue:
        current = queue.popleft()
        for dependent in dependents.get(current, set()):
            if dependent not in impacted:
                impacted.add(dependent)
                queue.append(dependent)
    return impacted


def resolve_cycles(edges: list[KnowledgeEdge]) -> list[KnowledgeEdge]:
    adjacency: dict[UUID, list[KnowledgeEdge]] = defaultdict(list)
    indegree: dict[UUID, int] = defaultdict(int)
    nodes: set[UUID] = set()

    for edge in edges:
        if not edge.active:
            continue
        adjacency[edge.from_node_id].append(edge)
        indegree[edge.to_node_id] += 1
        nodes.add(edge.from_node_id)
        nodes.add(edge.to_node_id)

    queue = deque(node for node in nodes if indegree[node] == 0)
    visited: set[UUID] = set()
    while queue:
        node = queue.popleft()
        visited.add(node)
        for edge in adjacency.get(node, []):
            indegree[edge.to_node_id] -= 1
            if indegree[edge.to_node_id] == 0:
                queue.append(edge.to_node_id)

    if visited == nodes:
        return edges

    remaining_nodes = nodes - visited
    candidates = [
        edge
        for edge in edges
        if edge.active and edge.from_node_id in remaining_nodes and edge.to_node_id in remaining_nodes
    ]
    if not candidates:
        return edges

    weakest = min(candidates, key=lambda edge: (edge.serving_confidence, edge.source_confidence))
    weakest.active = False
    weakest.cycle_break_reason = "lowest_trust_edge"
    return edges
