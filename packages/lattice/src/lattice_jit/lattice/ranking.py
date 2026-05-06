from __future__ import annotations

from collections import Counter

from lattice_jit.contracts import ConfidenceBand, KnowledgeNode


def rank_nodes_for_query(query: str, nodes: list[KnowledgeNode]) -> list[tuple[KnowledgeNode, float]]:
    query_terms = Counter(_normalize_terms(query))
    ranked: list[tuple[KnowledgeNode, float]] = []
    for node in nodes:
        body = f"{node.title}\n{node.body_text or ''}\n{node.source_uri or ''}"
        node_terms = Counter(_normalize_terms(body))
        node_len = sum(node_terms.values())
        overlap = sum(min(query_terms[term], count) for term, count in node_terms.items()) / max(node_len, 1)
        score = float(overlap) + node.serving_confidence
        if overlap > 0 or node.node_type.value == "source":
            ranked.append((node, score))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


def compute_confidence_band(nodes: list[KnowledgeNode]) -> ConfidenceBand:
    if not nodes:
        return ConfidenceBand.LOW
    floor = min(node.serving_confidence for node in nodes)
    if floor >= 0.8:
        return ConfidenceBand.HIGH
    if floor >= 0.6:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


def _normalize_terms(text: str) -> list[str]:
    return [term for term in "".join(ch if ch.isalnum() else " " for ch in text.lower()).split() if term]
