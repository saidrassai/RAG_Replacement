# Lattice-JIT v3.1 — FinanceBench Accuracy Plan

**Date:** April 29, 2026
**Baseline:** 47.64% composite with pdfplumber structured ingestion
**Target:** 90-95% composite on FinanceBench

## What we learned

| Approach | Result | Verdict |
|----------|--------|---------|
| pypdf2 extraction | 40.59% | Replaced |
| pdfplumber structured + ASCII tables | 47.64% | **Best baseline** |
| + LLM re-ranker | 44.19% | **Harmful** — removes good nodes |
| + Schema query injection | 35.06% | **Harmful** — dilutes retrieval |
| + Schema prompt injection | 36.59% | **Harmful** — distracts qualitative Qs |
| + Concept scoring boost | 36.71% | **No effect** — retrieval is fine |
| + Unit scaling fix | 39.17% | Helped scoring, retrieval unchanged |

**Root cause:** Not retrieval. DeepSeek v4 can't compute financial ratios from table data. A general-purpose LLM is the bottleneck.

## Phase 1 — Clean Revert to Baseline (30 min)

- [ ] Remove `_get_financial_boost_terms()` call from routing.py
- [ ] Remove schema grounding from service.py  
- [ ] Keep: pdfplumber, ASCII tables, section expansion, unit-scaling scoring
- [ ] Keep: `financial_schema.py` and `_llm_rerank_sections()` as reference code

**Target:** Clean 47.64% baseline, 109 tests passing.

## Phase 2 — Financial LLM Integration (2-3 days)

- [ ] Add HuggingFace model provider to ModelProvider (new backend)
- [ ] Evaluate `instruction-pretrain/finance-Llama3-8B` (off-shelf, CPT+SFT)
- [ ] Configure for local inference (CPU with quantization, or GPU)
- [ ] Run FinanceBench against finance model vs DeepSeek baseline

**Target:** 60-70% composite.

## Phase 3 — Prompt Engineering (if Phase 2 hits 60%+)

- [ ] Computation hints from financial_schema.py → system prompt
- [ ] Multi-hop reasoning template
- [ ] Real Phase B verification with number extraction + cross-reference

**Target:** 75-85% composite.

## Phase 4 — Fine-Tuning (if 85%+ achieved)

- [ ] Collect FinanceBench questions as training data
- [ ] LoRA fine-tune on 1× A100 (~$30)
- [ ] DPO alignment for preference optimization

**Target:** 90-95% composite.

## What we will NOT do

- Text-appending schema grounding to queries
- LLM re-ranking with short summaries
- Embedding model swap
- BM25 sparse retriever
- docling backend (reordered tables, gave wrong numbers)
