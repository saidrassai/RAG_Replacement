from __future__ import annotations

import math
from collections import Counter

from lattice_jit.contracts import ConfidenceBand, KnowledgeNode

# ── Known SEC filers for company-name boosting ─────────────────────────
_KNOWN_COMPANIES = [
    "3M", "Activision", "Blizzard", "Adobe", "AES Corporation", "Amazon",
    "Amcor", "AMD", "American Express", "American Water Works", "Best Buy",
    "Boeing", "Foot Locker",
]


def _extract_company_name(query: str) -> str | None:
    """Extract a known SEC filing company name from a financial query."""
    ql = query.lower()
    for c in sorted(_KNOWN_COMPANIES, key=len, reverse=True):
        if c.lower() in ql:
            return c
    return None


def rank_nodes_for_query(query: str, nodes: list[KnowledgeNode]) -> list[tuple[KnowledgeNode, float]]:
    """Rank nodes by TF‑IDF with company‑name filtering and boosting.

    If the query mentions a known company, pre-filter to only that company's nodes.
    Then rank remaining nodes by TF-IDF with company-name boosting.
    """
    query_terms = Counter(_normalize_terms(query))
    company = _extract_company_name(query)

    # ── Company-name pre-filter: only search the queried company's nodes ─
    if company:
        filtered = []
        for node in nodes:
            body = f"{node.title}\n{node.body_text or ''}\n{node.source_uri or ''}"
            if company.lower() in body.lower():
                filtered.append(node)
        if filtered:
            nodes = filtered

    N = len(nodes)

    # ── Compute IDF across all nodes ──────────────────────────────────
    df: Counter[str] = Counter()
    for node in nodes:
        body = f"{node.title}\n{node.body_text or ''}\n{node.source_uri or ''}"
        for term in set(_normalize_terms(body)):
            df[term] += 1

    idf: dict[str, float] = {}
    for term, count in df.items():
        idf[term] = math.log((N + 1.0) / (count + 1.0)) + 1.0

    # ── Company-name boost ────────────────────────────────────────────
    company = _extract_company_name(query)

    ranked: list[tuple[KnowledgeNode, float]] = []
    for node in nodes:
        body = f"{node.title}\n{node.body_text or ''}\n{node.source_uri or ''}"
        node_terms = Counter(_normalize_terms(body))
        total_node_terms = sum(node_terms.values()) or 1

        # TF‑IDF score
        tfidf_score = 0.0
        for term, q_count in query_terms.items():
            if term in node_terms:
                tf = node_terms[term] / total_node_terms
                tfidf_score += q_count * tf * idf.get(term, 0.0)

        # Company-name boost: +0.3 if the node body mentions the queried company
        boost = 0.0
        if company and company.lower() in body.lower():
            boost = 0.3

        score = tfidf_score + boost
        if tfidf_score > 0 or node.node_type.value == "source" or boost > 0:
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
