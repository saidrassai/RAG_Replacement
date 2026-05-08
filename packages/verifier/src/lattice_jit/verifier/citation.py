"""Citation framework for the Finance Agent Model.

Every numeric fact in an agent's answer must cite:
  - Source document (SEC filing, earnings release, database table)
  - Page number or data range
  - Table reference or query specification
  - Hyperlink to the source when available

Adopted from: Anthropic financial-services `earnings-analysis/SKILL.md`
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════════════════════════


class SourceType(str, Enum):
    """Classification of financial data sources."""

    SEC_FILING = "sec_filing"
    EARNINGS_RELEASE = "earnings_release"
    EARNINGS_TRANSCRIPT = "earnings_transcript"
    INVESTOR_PRESENTATION = "investor_presentation"
    DATABASE_QUERY = "database_query"
    SPREADSHEET = "spreadsheet"
    CALCULATION = "calculation"
    MARKET_DATA = "market_data"
    OTHER = "other"


@dataclass(slots=True)
class Citation:
    """A single source citation for a data point.

    Every numeric fact in an agent answer should reference one of these.
    """

    source_name: str  # e.g., "Amazon Q2 2024 10-Q"
    source_type: SourceType
    page: int | None = None  # PDF page number
    table_reference: str | None = None  # e.g., "Income Statement", "Table 3"
    row_range: str | None = None  # e.g., "rows 12-45" or "row 24"
    url: str | None = None  # SEC EDGAR link or database reference
    date_accessed: str | None = None  # ISO date when data was retrieved
    query_sql: str | None = None  # For database-sourced data

    def to_markdown(self) -> str:
        """Render citation as inline markdown reference."""
        parts = [self.source_name]
        if self.table_reference:
            parts.append(self.table_reference)
        if self.page is not None:
            parts.append(f"p.{self.page}")
        if self.row_range:
            parts.append(self.row_range)

        ref_text = ", ".join(parts)

        if self.url:
            return f'[{ref_text}]({self.url})'
        return ref_text

    def to_table_row(self) -> str:
        """Render citation as a table row for the Sources & References section."""
        source = self.source_name
        detail = ""
        if self.page is not None:
            detail += f"p.{self.page} "
        if self.table_reference:
            detail += self.table_reference
        if self.row_range:
            detail += f", {self.row_range}"

        link = f"[Link]({self.url})" if self.url else "—"

        return f"| {source} | {detail.strip() or '—'} | {self.date_accessed or '—'} | {link} |"


@dataclass
class CitationReport:
    """Aggregate citation report for an agent's answer."""

    citations: list[Citation] = field(default_factory=list)
    unsourced_claims: list[str] = field(default_factory=list)
    is_complete: bool = False

    @property
    def citation_count(self) -> int:
        return len(self.citations)

    @property
    def has_unsourced(self) -> bool:
        return len(self.unsourced_claims) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Citation Validator
# ═══════════════════════════════════════════════════════════════════════════════

# Pattern: "Source: {name}, p.{page}, {table}" or "[UNSOURCED]"
_CITATION_PATTERN = re.compile(
    r"Source:\s*(.+?)(?:\s*,\s*p\.?\s*(\d+))?(?:\s*,\s*(.+?))?(?:\n|$)",
    re.IGNORECASE,
)
_UNSOURCED_PATTERN = re.compile(r"\[UNSOURCED\]", re.IGNORECASE)
_NUMBER_PATTERN = re.compile(r"\$?[\d,]+\.?\d*\s*(?:million|billion|trillion|[MBT]|%)")


def validate_answer_citations(answer_text: str) -> CitationReport:
    """Scan an agent's answer and produce a citation completeness report.

    Flags:
      - Every number with a proper Source: citation
      - Unsourced claims marked with [UNSOURCED]
      - Sources & References section present
    """
    report = CitationReport()

    # Extract explicit citations
    for match in _CITATION_PATTERN.finditer(answer_text):
        source = match.group(1).strip()
        page = int(match.group(2)) if match.group(2) else None
        table = match.group(3).strip() if match.group(3) else None

        # Determine source type
        stype = _classify_source(source)

        report.citations.append(Citation(
            source_name=source,
            source_type=stype,
            page=page,
            table_reference=table,
        ))

    # Find unsourced claims
    for match in _UNSOURCED_PATTERN.finditer(answer_text):
        # Grab surrounding context for the unsourced claim
        start = max(0, match.start() - 80)
        end = min(len(answer_text), match.end() + 80)
        report.unsourced_claims.append(answer_text[start:end].strip())

    # Check for Sources & References section
    has_sources_section = "sources & references" in answer_text.lower()
    has_sources_header = "## sources" in answer_text.lower()

    # Report is complete if: has citations AND has sources section AND no unsourced
    report.is_complete = (
        len(report.citations) > 0
        and (has_sources_section or has_sources_header)
        and not report.has_unsourced
    )

    return report


def _classify_source(source_name: str) -> SourceType:
    """Classify a source string into its type."""
    lower = source_name.lower()
    if "10-k" in lower or "10-q" in lower or "8-k" in lower or "sec" in lower:
        return SourceType.SEC_FILING
    if "earnings release" in lower or "press release" in lower:
        return SourceType.EARNINGS_RELEASE
    if "transcript" in lower or "earnings call" in lower:
        return SourceType.EARNINGS_TRANSCRIPT
    if "presentation" in lower or "investor" in lower:
        return SourceType.INVESTOR_PRESENTATION
    if "sql" in lower or "query" in lower or "database" in lower or "ledger" in lower:
        return SourceType.DATABASE_QUERY
    if "xlsx" in lower or "spreadsheet" in lower or "csv" in lower or "excel" in lower:
        return SourceType.SPREADSHEET
    if "calculated" in lower or "computed" in lower or "formula" in lower:
        return SourceType.CALCULATION
    return SourceType.OTHER


# ═══════════════════════════════════════════════════════════════════════════════
# Sources & References Section Builder
# ═══════════════════════════════════════════════════════════════════════════════


def build_sources_section(citations: list[Citation], *, notes: str | None = None) -> str:
    """Build a Sources & References markdown section from citations.

    Args:
        citations: List of source citations.
        notes: Optional methodology notes or calculation formulas.

    Returns:
        Markdown-formatted Sources & References section.
    """
    if not citations:
        return ""

    # Group by source type
    sec_filings = [c for c in citations if c.source_type == SourceType.SEC_FILING]
    releases = [c for c in citations if c.source_type == SourceType.EARNINGS_RELEASE]
    transcripts = [c for c in citations if c.source_type == SourceType.EARNINGS_TRANSCRIPT]
    databases = [c for c in citations if c.source_type == SourceType.DATABASE_QUERY]
    calculations = [c for c in citations if c.source_type == SourceType.CALCULATION]
    others = [c for c in citations if c.source_type not in (
        SourceType.SEC_FILING, SourceType.EARNINGS_RELEASE,
        SourceType.EARNINGS_TRANSCRIPT, SourceType.DATABASE_QUERY,
        SourceType.CALCULATION,
    )]

    sections: list[str] = ["## Sources & References\n"]

    if sec_filings:
        sections.append("### SEC Filings\n")
        sections.append("| Source | Detail | Accessed | Link |\n|--------|--------|----------|------|")
        for c in sec_filings:
            sections.append(c.to_table_row())
        sections.append("")

    if releases:
        sections.append("### Earnings Releases\n")
        sections.append("| Source | Detail | Accessed | Link |\n|--------|--------|----------|------|")
        for c in releases:
            sections.append(c.to_table_row())
        sections.append("")

    if transcripts:
        sections.append("### Earnings Call Transcripts\n")
        sections.append("| Source | Detail | Accessed | Link |\n|--------|--------|----------|------|")
        for c in transcripts:
            sections.append(c.to_table_row())
        sections.append("")

    if databases:
        sections.append("### Database Queries\n")
        sections.append("| Source | Detail | Accessed | Link |\n|--------|--------|----------|------|")
        for c in databases:
            sections.append(c.to_table_row())
        sections.append("")

    if calculations:
        sections.append("### Calculations\n")
        for c in calculations:
            sections.append(f"- {c.source_name}")
            if c.table_reference:
                sections.append(f"  - Formula: `{c.table_reference}`")
        sections.append("")

    if others:
        sections.append("### Other Sources\n")
        sections.append("| Source | Detail | Accessed | Link |\n|--------|--------|----------|------|")
        for c in others:
            sections.append(c.to_table_row())
        sections.append("")

    if notes:
        sections.append(f"### Methodology Notes\n{notes}\n")

    sections.append("*All source documents retrieved at time of query. Data may not reflect subsequent filings.*")

    return "\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════════
# Agent System Prompt Template
# ═══════════════════════════════════════════════════════════════════════════════


AGENT_SYSTEM_PROMPT = """You are a Finance Data Scientist Agent built on Qwen3.5-9B.

## CAPABILITIES
- Deep search across SEC filings, earnings transcripts, databases, spreadsheets
- SQL generation and execution on financial databases
- Statistical analysis: YoY, MoM, trend, variance, correlation, regression, forecasting
- Chart generation: bar, line, histogram, scatter, grouped_bar, stacked_bar, heatmap
- Multi-step financial calculation with explicit formulas
- Source citation: every number cites source, page, table reference, and hyperlink

## REQUIRED WORKFLOW (5 Phases)

**PLAN** — Identify data sources and tools needed. No tool calls yet.
**COLLECT** — Execute all data retrieval tool calls.
**ANALYZE** — Compute metrics, find trends, compare periods, flag discrepancies.
**VISUALIZE** — Generate charts when requested or when comparison benefits from visualization.
**VERIFY** — Cross-validate numbers, complete citations, run quality checklist before final answer.

NEVER skip phases. PLAN before COLLECT. COLLECT before ANALYZE.
ANALYZE before VISUALIZE. VERIFY before final output.

## CITATION REQUIREMENTS (MANDATORY)

Every numeric fact must include inline citation:
  Source: {Document Name}, p.{Page}, {Table Reference}

Format:
  "Revenue was $90.0B, up 9.1% from $82.5B.
   Source: Amazon Q2 2024 10-Q, p.24, Income Statement"

Every final answer MUST end with a Sources & References section:
  ## Sources & References

  ### SEC Filings
  | Source | Detail | Accessed | Link |
  |--------|--------|----------|------|
  | Amazon Q2 2024 10-Q | p.24 Income Statement | 2026-05-06 | [Link](https://...) |
  | Amazon Q2 2023 10-Q | p.24 Income Statement | 2026-05-06 | [Link](https://...) |

  ### Database Queries
  | Source | Detail | Accessed | Link |
  |--------|--------|----------|------|
  | general_ledger | SELECT region, SUM(revenue)... | 2026-05-06 | — |

  ### Calculations
  - YoY Revenue Growth: (90,033 - 82,541) / 82,541 × 100 = 9.08%

## GUARDRAILS

- NO automated transaction execution or ledger posting
- Unsourced claims must be flagged with [UNSOURCED]
- If source is unavailable, state clearly: "Source not accessible at time of query"
- Never invent figures — if data is missing, say so
- Every answer footer: "AI-generated analysis. Human review required."

## OUTPUT FORMAT

Answer in professional markdown with:
1. Executive summary (2-3 sentences)
2. Detailed analysis with inline citations
3. Charts inline where generated
4. Sources & References section (MANDATORY)
5. Disclaimer footer: "AI-generated analysis. Human review required. Not financial advice."

## EXAMPLES

**Good citation:**
The company reported Q2 2024 revenue of $148.8 billion, up 11% year-over-year.
Source: Apple Q2 2024 10-Q, p.3, Consolidated Statements of Operations

**Bad citation (INVALID):**
Revenue was $148.8 billion, up 11%.
[NO SOURCE — this would be flagged [UNSOURCED]]
"""
