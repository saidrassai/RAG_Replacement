"""Financial Schema Grounding — bridges the vocabulary gap between
textbook financial terminology and SEC filing language.

FinanceBench questions use academic/computational terms (DPO, fixed asset
turnover ratio) that never appear verbatim in 10-K/10-Q filings. This module
maps those concepts to the language actually used in SEC documents so our
retrieval layer can find the right pages.

Design: purely additive — injects grounded terms into the query before
retrieval. Zero architectural changes. Does not modify the graph, router,
or compiler. Just makes queries speak the same language as the documents.
"""

from __future__ import annotations

# ── Financial Concept → SEC Filing Terminology ──────────────────────────────
# Each entry: (concept_keywords, sec_search_terms, computation_hint)
# The LLM uses computation_hint when the answer requires calculation.

FINANCIAL_CONCEPTS: list[tuple[list[str], list[str], str]] = [
    # ── Balance Sheet Metrics ────────────────────────────────────────────
    (
        ["capital expenditure", "capex", "capital spending"],
        ["property plant and equipment", "purchases of property", "capital additions",
         "acquisition of property", "ppe additions", "investing activities"],
        "Find the exact dollar amount under 'Capital expenditures' or 'Purchases of PP&E' "
        "in the cash flow statement or PP&E note."
    ),
    (
        ["fixed asset turnover", "fixed asset", "ppe turnover"],
        ["property plant and equipment net", "net sales", "revenue",
         "net property", "total net sales"],
        "Compute: Net Sales ÷ Average Net Fixed Assets (PP&E). Find both numbers in "
        "the income statement (sales/revenue) and balance sheet (PP&E, net)."
    ),
    (
        ["quick ratio", "acid test"],
        ["cash and cash equivalents", "current assets", "current liabilities",
         "short-term investments", "accounts receivable"],
        "Compute: (Cash + Short-term Investments + Accounts Receivable) ÷ Current Liabilities. "
        "Find these values on the balance sheet."
    ),
    (
        ["working capital", "net working capital"],
        ["current assets", "current liabilities", "working capital",
         "total current assets", "total current liabilities"],
        "Compute: Current Assets − Current Liabilities. Both on the balance sheet."
    ),
    (
        ["total asset", "asset size", "total assets"],
        ["total assets", "total consolidated assets", "balance sheet",
         "assets", "consolidated balance sheets"],
        "Find the exact number on the balance sheet under 'Total assets'."
    ),
    (
        ["cash and cash equivalent", "cash balance", "cash position"],
        ["cash and cash equivalents", "cash", "cash equivalents",
         "balance sheet", "consolidated balance sheets"],
        "Find on the balance sheet under 'Cash and cash equivalents'."
    ),

    # ── Income Statement Metrics ──────────────────────────────────────────
    (
        ["effective tax rate", "tax rate", "income tax rate"],
        ["income tax expense", "income before income taxes", "provision for income taxes",
         "effective tax rate", "earnings before income taxes"],
        "Compute: Income Tax Expense ÷ Income Before Income Taxes. Find both in the "
        "income statement or tax footnote. Multiply by 100 for percentage."
    ),
    (
        ["net income", "net earnings", "net profit"],
        ["net income", "net earnings", "consolidated net income",
         "income statement", "statement of operations"],
        "Find on the income statement under 'Net income' or 'Net earnings'."
    ),
    (
        ["revenue", "total revenue", "sales", "net sales"],
        ["net sales", "total revenue", "revenue", "total net revenue",
         "income statement", "consolidated statements of operations"],
        "Find the top line of the income statement."
    ),
    (
        ["operating income", "operating profit", "ebit"],
        ["operating income", "income from operations", "operating earnings",
         "earnings before interest and taxes"],
        "Find on the income statement under 'Operating income'."
    ),
    (
        ["gross profit", "gross margin"],
        ["gross profit", "cost of goods sold", "cost of sales",
         "gross margin", "net sales"],
        "Compute: (Net Sales − Cost of Goods Sold) ÷ Net Sales."
    ),
    (
        ["cost of goods sold", "cogs", "cost of sales"],
        ["cost of goods sold", "cost of sales", "cost of revenue",
         "income statement"],
        "Find on the income statement."
    ),
    (
        ["restructuring cost", "restructuring charge", "restructuring"],
        ["restructuring", "restructuring charges", "restructuring and related",
         "restructuring costs", "restructuring activities", "severance"],
        "Find in the MD&A or notes to financial statements."
    ),

    # ── Efficiency / Turnover Ratios ──────────────────────────────────────
    (
        ["days payable outstanding", "dpo", "payable days"],
        ["accounts payable", "cost of goods sold", "cost of sales",
         "trade payables", "average accounts payable"],
        "Compute: 365 × Average Accounts Payable ÷ Cost of Goods Sold. "
        "Find AP on balance sheet, COGS on income statement."
    ),
    (
        ["days sales outstanding", "dso", "receivable days"],
        ["accounts receivable", "net sales", "trade receivables",
         "average accounts receivable", "revenue"],
        "Compute: 365 × Average Accounts Receivable ÷ Net Sales."
    ),
    (
        ["inventory turnover", "inventory days", "dio"],
        ["inventory", "cost of goods sold", "inventories",
         "average inventory"],
        "Compute: Cost of Goods Sold ÷ Average Inventory."
    ),
    (
        ["asset turnover", "total asset turnover"],
        ["net sales", "total assets", "average total assets", "revenue"],
        "Compute: Net Sales ÷ Average Total Assets."
    ),

    # ── Profitability Ratios ──────────────────────────────────────────────
    (
        ["return on equity", "roe"],
        ["net income", "shareholders equity", "stockholders equity",
         "total equity", "average equity"],
        "Compute: Net Income ÷ Average Shareholders' Equity."
    ),
    (
        ["return on assets", "roa"],
        ["net income", "total assets", "average total assets"],
        "Compute: Net Income ÷ Average Total Assets."
    ),
    (
        ["net interest margin", "nim"],
        ["net interest income", "interest income", "interest expense",
         "average earning assets", "yield"],
        "Find in the financial review or MD&A section."
    ),
    (
        ["efficiency ratio"],
        ["noninterest expense", "net revenue", "total revenue",
         "operating expense", "efficiency ratio"],
        "Compute: Non-Interest Expense ÷ Net Revenue."
    ),

    # ── Market / Valuation ────────────────────────────────────────────────
    (
        ["diluted eps", "earnings per share", "eps"],
        ["diluted earnings per share", "basic earnings per share",
         "net income per share", "diluted eps"],
        "Find on the income statement under 'Earnings per share'."
    ),
    (
        ["dividend", "dividend per share", "shareholder return"],
        ["dividends declared", "dividends per share", "common stock dividends",
         "share repurchase", "returned to shareholders"],
        "Find in the capital management or shareholder return section."
    ),
    (
        ["share repurchase", "stock buyback", "buyback"],
        ["share repurchase", "repurchased shares", "common stock repurchases",
         "treasury stock", "stock buyback"],
        "Find in the capital management or financing activities section."
    ),

    # ── Risk / Qualitative ────────────────────────────────────────────────
    (
        ["cyclicality", "cyclical", "business cycle"],
        ["cyclical", "seasonal", "subject to fluctuation", "economic conditions",
         "market conditions", "risk factor", "business environment"],
        "Check the Risk Factors and Business sections for discussion of cyclicality."
    ),
    (
        ["liquidity", "liquidity profile", "liquidity position"],
        ["liquidity and capital resources", "liquidity", "capital resources",
         "cash and cash equivalents", "available liquidity", "credit facilities"],
        "Check the MD&A 'Liquidity and Capital Resources' section."
    ),
    (
        ["debt security", "registered debt", "debt instrument"],
        ["notes", "senior notes", "debt securities", "registered under",
         "indenture", "floating rate notes", "fixed rate notes"],
        "Check the debt footnote or 'Borrowings' section of the 10-K."
    ),
    (
        ["ceo", "chief executive", "executive officer", "new ceo"],
        ["chief executive officer", "appointed", "named", "executive officer",
         "management", "board of directors", "employment agreement"],
        "Check the 8-K filing or 'Executive Officers' section of the 10-K."
    ),
    (
        ["cybersecurity", "security incident", "data breach", "cyber"],
        ["cybersecurity", "information security", "data protection",
         "security breach", "cyber incident", "technology risk"],
        "Check Risk Factors and MD&A sections."
    ),

    # ── Document Structure ────────────────────────────────────────────────
    (
        ["10-k", "annual report", "fiscal year"],
        ["form 10-k", "annual report", "fiscal year ended",
         "management's discussion", "financial statements"],
        "Look for the 10-K filing, typically 100+ pages with specific sections."
    ),
    (
        ["10-q", "quarterly report", "quarter"],
        ["form 10-q", "quarterly report", "quarter ended",
         "unaudited", "interim financial statements"],
        "Look for the 10-Q filing, shorter than 10-K."
    ),
    (
        ["8-k", "current report", "filing dated"],
        ["form 8-k", "current report", "filed on",
         "dated", "furnished", "press release"],
        "8-K filings are short event-driven documents."
    ),
]


def ground_query(query: str) -> str:
    """Expand a query with SEC filing terminology for better retrieval.

    If the query contains recognized financial concepts, appends the
    SEC-equivalent search terms so our retrieval layer finds the right pages.

    Example:
        "What is the fixed asset turnover ratio for FY2019?"
        → "... [Ground: Search for: property plant and equipment net, net sales,
           revenue, net property, total net sales. Computation hint: Compute
           Net Sales / Avg Net Fixed Assets from balance sheet and income stmt.]"
    """
    query_lower = query.lower()
    matched_terms: list[str] = []
    computation_hints: list[str] = []

    for keywords, sec_terms, hint in FINANCIAL_CONCEPTS:
        if any(kw in query_lower for kw in keywords):
            matched_terms.extend(sec_terms[:5])
            if hint and hint not in computation_hints:
                computation_hints.append(hint)

    if not matched_terms:
        return query

    unique_terms = list(dict.fromkeys(matched_terms))[:15]
    grounding = (
        "\n\n[Financial Schema Ground: The query involves these financial concepts. "
        "When searching the document, look for these SEC filing terms: "
        + ", ".join(unique_terms)
        + "."
    )
    if computation_hints:
        grounding += " Computation guidance: " + " | ".join(computation_hints[:3]) + "]"

    return query + grounding


def extract_financial_entities(text: str) -> dict[str, list[str]]:
    """Extract financial entities from text for structured retrieval.

    Returns dict with keys: companies, years, metrics, amounts.
    Useful for building structured queries against the knowledge graph.
    """
    import re

    entities: dict[str, list[str]] = {"metrics": [], "years": [], "amounts": []}

    # Financial metrics from our schema
    for keywords, _, _ in FINANCIAL_CONCEPTS:
        if any(kw in text.lower() for kw in keywords):
            entities["metrics"].append(keywords[0])

    # Years
    years = re.findall(r"(?:FY|Fiscal Year)\s*(\d{4})", text, re.IGNORECASE)
    entities["years"] = years or re.findall(r"\b(20\d{2})\b", text)

    # Dollar amounts
    amounts = re.findall(r"\$[\d,]+\.?\d*\s*(?:billion|million|thousand)?", text, re.IGNORECASE)
    entities["amounts"] = amounts

    return entities
