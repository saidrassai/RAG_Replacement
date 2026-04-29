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


def _get_financial_boost_terms(query: str) -> list[str]:
    """Get SEC filing search terms for financial concepts in the query.

    Returns a list of terms that should boost a node's score if found
    in the node text. Does NOT modify the query — used only for scoring.
    """
    terms: list[str] = []
    ql = query.lower()
    # Mapping: query keywords → SEC filing terms to look for in nodes
    mappings = {
        "capital expenditure": ["capital expenditures", "property plant and equipment", "purchases of property"],
        "capex": ["capital expenditures", "purchases of property"],
        "fixed asset turnover": ["property plant and equipment net", "net sales"],
        "dpo": ["accounts payable", "cost of goods sold", "cost of sales"],
        "days payable": ["accounts payable", "cost of goods sold"],
        "quick ratio": ["cash and cash equivalents", "current assets", "current liabilities"],
        "liquidity": ["liquidity and capital resources", "current assets", "current liabilities"],
        "working capital": ["current assets", "current liabilities"],
        "effective tax rate": ["income tax expense", "income before income taxes"],
        "return on equity": ["net income", "shareholders equity", "stockholders equity"],
        "roe": ["net income", "shareholders equity"],
        "return on assets": ["net income", "total assets"],
        "roa": ["net income", "total assets"],
        "restructuring": ["restructuring charges", "restructuring and related"],
        "eps": ["earnings per share", "diluted earnings per share"],
        "dividend": ["dividends declared", "dividends per share", "share repurchase"],
        "cyclical": ["cyclical", "seasonal", "subject to fluctuation"],
        "ceo": ["chief executive officer", "executive officer", "appointed"],
        "debt securities": ["senior notes", "notes", "registered under"],
        "cybersecurity": ["cybersecurity", "information security", "data breach"],
        "net zero": ["net-zero", "greenhouse gas", "emissions"],
        "sustainable": ["sustainable finance", "green", "esg", "climate"],
        "var": ["value-at-risk", "var", "trading portfolio"],
        "diluted eps": ["diluted earnings per share", "earnings per share"],
        "net income": ["net income", "net earnings", "consolidated net income"],
        "revenue": ["net sales", "total revenue", "revenue"],
        "asset size": ["total assets", "total consolidated assets"],
        "employees": ["employees", "full-time", "workforce"],
        "branches": ["branches", "retail branches", "locations"],
        "cet1": ["common equity tier 1", "cet1", "risk-weighted assets"],
        "leverage ratio": ["leverage ratio", "tier 1 leverage", "supplementary leverage"],
        "lcr": ["liquidity coverage ratio", "high-quality liquid assets", "hqla"],
        "nsfr": ["net stable funding ratio", "available stable funding"],
        "g-sib": ["global systemically important", "g-sib", "surcharge"],
        "basel iii": ["basel iii", "risk-weighted assets", "capital conservation buffer"],
        "sec rule": ["rule 17a-4", "sec", "securities and exchange commission"],
        "gdpr": ["gdpr", "general data protection", "personal data", "data subject"],
        "sox": ["sarbanes-oxley", "internal control", "section 302", "section 404"],
        "pci": ["pci dss", "cardholder data", "payment card industry"],
        "kyc": ["know your customer", "customer due diligence", "cdd"],
        "audit log": ["audit log", "audit trail", "log retention"],
        "password": ["password", "authentication", "multi-factor", "mfa"],
        "lockout": ["lockout", "failed attempts", "account lock"],
    }
    for kw, sec_terms in mappings.items():
        if kw in ql:
            terms.extend(sec_terms[:5])
    return list(dict.fromkeys(terms))  # deduplicate, preserve order


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
