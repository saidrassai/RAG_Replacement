from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from lattice_jit.contracts import KnowledgeNode
from lattice_jit.lattice import rank_nodes_for_query


@dataclass(slots=True)
class SemanticRouter:
    max_nodes: int = 8

    def select(self, query: str, nodes: list[KnowledgeNode], subgraph_ids: list[UUID] | None) -> list[KnowledgeNode]:
        if subgraph_ids:
            selected = [node for node in nodes if node.node_id in set(subgraph_ids)]
            if selected:
                return selected[: self.max_nodes]
        ranked = rank_nodes_for_query(query, nodes)
        selected = [node for node, _score in ranked[: self.max_nodes]]
        if selected:
            return selected
        return nodes[: self.max_nodes]
