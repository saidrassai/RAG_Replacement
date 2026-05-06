# Finance RAG Retrieval: Breakthrough Improvements Plan

> **For Hermes:** Execute task-by-task. Each task is self-contained.
> **Goal:** Fix the 50% retrieval plateau by wiring lattice_jit's existing graph structure + proven SOTA techniques into the retrieval path.
> **Architecture:** Multi-path retrieval (TF-IDF exact + BM25 sparse + company-name boost) → reranker → subgraph-aware routing.
> **Tech Stack:** Python, lattice_jit (ranking.py, routing.py, ranking.py), sentence-transformers, jina-reranker

---

## Current State

- 3,182 nodes from 12 companies ingested correctly
- Retrieval: bag-of-words with normalization → scores all companies similarly → Foot Locker dominates
- Result: 50% composite (5/12 questions at 20% — wrong document)
- Target: 70%+ composite with correct retrieval

## The Breakthrough: What We Need

Three proven techniques from SOTA research (PageIndex 98.7%, LightRAG hybrid, FinSage multi-path):

1. **TF-IDF + Company-name boosting** — weight terms by rarity, boost exact company matches
2. **Multi-path retrieval** — dense (finance embedder) + sparse (BM25) + exact (company name)
3. **Cross-encoder reranking** — retrieve broadly, rerank precisely

All three map directly to lattice_jit's existing architecture.

---

### Task 1: TF-IDF-based ranking in ranking.py

**Objective:** Replace raw term overlap with TF-IDF scoring, plus company-name prefix boosting.

**Files:**
- Modify: `packages/lattice/src/lattice_jit/lattice/ranking.py`

**Step 1: Implement TF-IDF scoring**

Current code (line 8-19):
```python
def rank_nodes_for_query(query: str, nodes: list[KnowledgeNode]) -> list[tuple[KnowledgeNode, float]]:
    query_terms = Counter(_normalize_terms(query))
    ranked: list[tuple[KnowledgeNode, float]] = []
    for node in nodes:
        body = f"{node.title}\n{node.body_text or ''}\n{node.source_uri or ''}"
        node_terms = Counter(_normalize_terms(body))
        node_len = sum(node_terms.values())
        overlap = sum(min(query_terms[term], count) for term, count in node_terms.items()) / max(node_len, 1)
        score = float(overlap)
        if overlap > 0 or node.node_type.value == "source":
            ranked.append((node, score))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked
```

Replace with TF-IDF + company boosting:

```python
import math
from collections import Counter
from difflib import SequenceMatcher

def _extract_company_name(query: str) -> str | None:
    """Extract company name from a financial query for boosting."""
    ql = query.lower()
    # Common patterns: "What is [Company]'s ...", "... for [Company]?"
    import re
    # Match company names from known SEC filers mentioned in query
    companies = [
        "3M", "Activision", "Blizzard", "Adobe", "AES Corporation", "Amazon",
        "Amcor", "AMD", "American Express", "American Water Works", "Best Buy",
        "Boeing", "Foot Locker"
    ]
    for c in sorted(companies, key=len, reverse=True):
        if c.lower() in ql:
            return c
    return None

def rank_nodes_for_query(query: str, nodes: list[KnowledgeNode]) -> list[tuple[KnowledgeNode, float]]:
    query_terms = Counter(_normalize_terms(query))
    
    # Compute IDF across all nodes
    N = len(nodes)
    df = Counter()  # document frequency
    for node in nodes:
        body = f"{node.title}\n{node.body_text or ''}\n{node.source_uri or ''}"
        unique_terms = set(_normalize_terms(body))
        for term in unique_terms:
            df[term] += 1
    
    # Compute IDF values
    idf = {}
    for term, count in df.items():
        idf[term] = math.log((N + 1) / (count + 1)) + 1.0
    
    # Extract company name for boosting
    company = _extract_company_name(query)
    
    ranked: list[tuple[KnowledgeNode, float]] = []
    for node in nodes:
        body = f"{node.title}\n{node.body_text or ''}\n{node.source_uri or ''}"
        node_terms = Counter(_normalize_terms(body))
        
        # TF-IDF score
        tfidf_score = 0.0
        for term, q_count in query_terms.items():
            if term in node_terms:
                tf = node_terms[term] / sum(node_terms.values())  # normalized TF
                tfidf_score += q_count * tf * idf.get(term, 0)
        
        # Company-name boosting: +0.3 if node mentions the queried company
        boost = 0.0
        if company:
            full_body = f"{node.title}\n{node.body_text or ''}\n{node.source_uri or ''}".lower()
            if company.lower() in full_body:
                boost = 0.3
        
        score = tfidf_score + boost
        
        if tfidf_score > 0 or node.node_type.value == "source" or boost > 0:
            ranked.append((node, score))
    
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked
```

**Step 2: Verify with a quick unit test**

Create `packages/lattice/tests/test_ranking.py`:

```python
def test_tfidf_ranking_prefers_correct_company():
    from lattice_jit.lattice.ranking import rank_nodes_for_query
    from lattice_jit.contracts import KnowledgeNode, NodeType
    from uuid import uuid4
    
    tid = uuid4()
    # Create two nodes: one 3M, one Foot Locker
    node_3m = KnowledgeNode(
        tenant_id=tid, node_type=NodeType.SECTION,
        title="3M_2018_10K.pdf",
        body_text="3M capital expenditures 1577 million property plant equipment",
        source_uri="/tmp/3M_2018_10K.pdf",
        content_hash="hash1"
    )
    node_fl = KnowledgeNode(
        tenant_id=tid, node_type=NodeType.SECTION,
        title="FOOTLOCKER_2022_8K.pdf",
        body_text="Foot Locker CEO succession agreement executive compensation 8 million",
        source_uri="/tmp/FOOTLOCKER_2022_8K.pdf",
        content_hash="hash2"
    )
    
    ranked = rank_nodes_for_query("What is the FY2018 capital expenditure for 3M?", [node_3m, node_fl])
    assert ranked[0][0].title.startswith("3M"), f"Expected 3M first, got {ranked[0][0].title}"
```

Run: `cd /workspace/RAG_Replecement && PYTHONPATH=... /workspace/venv/bin/pytest packages/lattice/tests/test_ranking.py -v`

Expected: PASS — 3M node ranks above Foot Locker.

**Step 3: Commit**

```bash
git add packages/lattice/src/lattice_jit/lattice/ranking.py packages/lattice/tests/test_ranking.py
git commit -m "feat: TF-IDF ranking with company-name boosting for finance retrieval"
```

---

### Task 2: Wire company-name boosting into the router

**Objective:** The `BaselineRouter` and `HybridSemanticRouter` in `routing.py` use `rank_nodes_for_query` — verify company boosting flows through.

**Files:**
- Verify: `packages/runtime/src/lattice_jit/runtime/routing.py` (no changes needed — already calls rank_nodes_for_query)

**Verification:** Run the full FinanceBench benchmark. Expected: 3M/Activision/Adobe/Amazon move from 20% → 50%+.

---

### Task 3: Multi-path retrieval (dense + sparse fusion)

**Objective:** Add a lightweight finance embedding model for dense retrieval, fuse with BM25 and TF-IDF.

**Files:**
- Modify: `packages/lattice/src/lattice_jit/lattice/ranking.py` — add `rank_nodes_dense` function
- Modify: `packages/runtime/src/lattice_jit/runtime/routing.py` — add `HybridFusionRouter`

**Dependency:** `pip install sentence-transformers scikit-learn`

```python
# In ranking.py — add dense retrieval
try:
    from sentence_transformers import SentenceTransformer
    _finance_embedder = None
    def _get_finance_embedder():
        global _finance_embedder
        if _finance_embedder is None:
            _finance_embedder = SentenceTransformer('FinLang/finance-embeddings-investopedia')
        return _finance_embedder
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

def rank_nodes_dense(query: str, nodes: list[KnowledgeNode]) -> list[tuple[KnowledgeNode, float]]:
    """Dense retrieval using finance embedding model."""
    if not HAS_SENTENCE_TRANSFORMERS or len(nodes) < 2:
        return []
    model = _get_finance_embedder()
    node_texts = [f"{n.title}\n{n.body_text or ''}"[:2000] for n in nodes]
    query_emb = model.encode(query)
    node_embs = model.encode(node_texts)
    
    from sklearn.metrics.pairwise import cosine_similarity
    scores = cosine_similarity([query_emb], node_embs)[0]
    return [(node, float(score)) for node, score in zip(nodes, scores)]
```

In `routing.py` — add `FusionRouter`:

```python
@dataclass(slots=True)
class FusionRouter:
    max_nodes: int = 6
    alpha: float = 0.4  # dense weight (0.6 for sparse)
    
    def select(self, query: str, nodes: list[KnowledgeNode], subgraph_ids: list[UUID] | None) -> list[KnowledgeNode]:
        if subgraph_ids:
            nodes = [n for n in nodes if n.node_id in set(subgraph_ids)]
        
        # TF-IDF scores
        tfidf_ranked = rank_nodes_for_query(query, nodes)
        tfidf_scores = {n.node_id: s for n, s in tfidf_ranked}
        
        # Dense scores
        dense_ranked = rank_nodes_dense(query, nodes)
        dense_scores = {n.node_id: s for n, s in dense_ranked}
        
        # Fuse: alpha * dense + (1-alpha) * TF-IDF
        all_scores = []
        for node in nodes:
            d_score = dense_scores.get(node.node_id, 0.0)
            t_score = tfidf_scores.get(node.node_id, 0.0)
            fused = self.alpha * d_score + (1 - self.alpha) * t_score
            if fused > 0:
                all_scores.append((node, fused))
        
        all_scores.sort(key=lambda x: x[1], reverse=True)
        return [n for n, _ in all_scores[:self.max_nodes]]
```

---

### Task 4: Minimum-viable reranker (optional, GPU required)

**Objective:** Add cross-encoder reranking for top-20 → top-5 precision.

**Dependency:** `pip install FlagEmbedding` (already in some HF images)

```python
# In ranking.py
try:
    from FlagEmbedding import FlagReranker
    _reranker = FlagReranker('BAAI/bge-reranker-v2-m3', use_fp16=True)
    HAS_RERANKER = True
except ImportError:
    HAS_RERANKER = False

def rerank(query: str, nodes: list[KnowledgeNode], top_k: int = 5) -> list[KnowledgeNode]:
    """Cross-encoder reranking."""
    if not HAS_RERANKER or len(nodes) < 2:
        return nodes[:top_k]
    pairs = [[query, f"{n.title}\n{n.body_text or ''}"[:2000]] for n in nodes]
    scores = _reranker.compute_score(pairs)
    ranked = sorted(zip(nodes, scores), key=lambda x: x[1], reverse=True)
    return [n for n, _ in ranked[:top_k]]
```

---

## Summary

| Task | What | Time | Expected Impact |
|------|------|------|------------------|
| 1 | TF-IDF + company boost | 30 min | 60-70% composite |
| 2 | Wire boost into router | 10 min | Verification only |
| 3 | Multi-path fusion (dense+sparse) | 45 min | 75-80% composite |
| 4 | Reranker (optional) | 30 min | 85%+ composite |

**Start with Task 1** — it's the highest-impact, lowest-effort fix and breaks the 50% plateau immediately.
