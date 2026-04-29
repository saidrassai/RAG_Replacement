from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from lattice_jit.contracts import KnowledgeNode
from lattice_jit.lattice import rank_nodes_for_query

if TYPE_CHECKING:
    from .embedding import EmbeddingService


class RouterBackend(Protocol):
    def select(self, query: str, nodes: list[KnowledgeNode], subgraph_ids: list[UUID] | None) -> list[KnowledgeNode]:
        ...


@dataclass(slots=True)
class BaselineRouter:
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


@dataclass(slots=True)
class HybridSemanticRouter:
    max_nodes: int = 8
    embedding_service: EmbeddingService | None = field(default=None)

    def select(self, query: str, nodes: list[KnowledgeNode], subgraph_ids: list[UUID] | None) -> list[KnowledgeNode]:
        if subgraph_ids:
            selected = [node for node in nodes if node.node_id in set(subgraph_ids)]
            if selected:
                return selected[: self.max_nodes]

        baseline_ranked = rank_nodes_for_query(query, nodes)
        baseline_by_id = {node.node_id: score for node, score in baseline_ranked}
        max_baseline = max(baseline_by_id.values(), default=0.0)

        query_terms = _normalize_terms(query)
        query_text = " ".join(query_terms)

        use_embeddings = self.embedding_service is not None and self.embedding_service.enabled

        if use_embeddings:
            texts = [query_text] + [_node_text(node) for node in nodes]
            embeddings = self.embedding_service.encode(texts)  # type: ignore[union-attr]
            query_embedding = embeddings[0]
            node_embeddings = embeddings[1:]
            from .embedding import cosine_similarity

        scored: list[tuple[KnowledgeNode, float]] = []
        for idx, node in enumerate(nodes):
            node_text = _node_text(node)
            if use_embeddings:
                emb_sim = cosine_similarity(query_embedding, node_embeddings[idx])
                semantic_score = max(0.0, emb_sim)
            else:
                semantic_score = _semantic_similarity(query_text, query_terms, node_text)

            baseline_raw = baseline_by_id.get(node.node_id, 0.0)
            baseline_score = baseline_raw / max_baseline if max_baseline > 0 else 0.0
            score = 0.65 * semantic_score + 0.25 * baseline_score + 0.10 * node.serving_confidence

            if semantic_score > 0 or baseline_raw > 0 or node.node_type.value == "source":
                scored.append((node, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        selected = [node for node, _score in scored[: self.max_nodes]]
        if selected:
            return selected

        return BaselineRouter(max_nodes=self.max_nodes).select(query, nodes, None)


@dataclass(slots=True)
class SemanticRouter:
    max_nodes: int = 8
    mode: str = "baseline"
    backend_kwargs: dict[str, object] = field(default_factory=dict)

    def _backend(self) -> RouterBackend:
        if self.mode.lower() == "hybrid":
            return HybridSemanticRouter(max_nodes=self.max_nodes, **self.backend_kwargs)  # type: ignore[arg-type]
        return BaselineRouter(max_nodes=self.max_nodes)

    def select(self, query: str, nodes: list[KnowledgeNode], subgraph_ids: list[UUID] | None) -> list[KnowledgeNode]:
        return self._backend().select(query, nodes, subgraph_ids)


def _node_text(node: KnowledgeNode) -> str:
    return f"{node.title}\n{node.body_text or ''}\n{node.source_uri or ''}".strip()


def _normalize_terms(text: str) -> list[str]:
    return [term for term in "".join(ch if ch.isalnum() else " " for ch in text.lower()).split() if term]


def _semantic_similarity(query_text: str, query_terms: list[str], node_text: str) -> float:
    node_terms = _normalize_terms(node_text)
    if not node_terms or not query_terms:
        return 0.0

    query_set = set(query_terms)
    node_set = set(node_terms)
    term_jaccard = _jaccard(query_set, node_set)
    char_jaccard = _jaccard(_char_ngrams(query_text, 3), _char_ngrams(" ".join(node_terms), 3))
    fuzzy = SequenceMatcher(None, query_text, " ".join(node_terms)).ratio()
    return (0.45 * term_jaccard) + (0.35 * char_jaccard) + (0.20 * fuzzy)


def _char_ngrams(text: str, size: int) -> set[str]:
    collapsed = "".join(ch for ch in text.lower() if ch.isalnum())
    if len(collapsed) < size:
        return {collapsed} if collapsed else set()
    return {collapsed[idx : idx + size] for idx in range(len(collapsed) - size + 1)}


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    union = left_set | right_set
    if not union:
        return 0.0
    return len(left_set & right_set) / len(union)
