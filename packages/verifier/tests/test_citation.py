"""Tests for the citation framework.

Run with: PYTHONPATH=... pytest packages/verifier/tests/test_citation.py -v
"""

from lattice_jit.verifier.citation import (
    Citation,
    CitationReport,
    SourceType,
    build_sources_section,
    validate_answer_citations,
    AGENT_SYSTEM_PROMPT,
)


class TestCitation:
    """Unit tests for Citation data type."""

    def test_to_markdown(self):
        """Citation renders as inline markdown reference."""
        c = Citation(
            source_name="Amazon Q2 2024 10-Q",
            source_type=SourceType.SEC_FILING,
            page=24,
            table_reference="Income Statement",
        )
        md = c.to_markdown()
        assert "Amazon Q2 2024 10-Q" in md
        assert "Income Statement" in md
        assert "p.24" in md

    def test_to_markdown_with_url(self):
        """Citation includes hyperlink when URL present."""
        c = Citation(
            source_name="Amazon Q2 2024 10-Q",
            source_type=SourceType.SEC_FILING,
            page=24,
            url="https://www.sec.gov/Archives/edgar/data/1018724/...",
        )
        md = c.to_markdown()
        assert "[" in md and "](" in md  # Markdown link syntax

    def test_to_table_row(self):
        """Citation renders as table row for Sources section."""
        c = Citation(
            source_name="Amazon Q2 2024 10-Q",
            source_type=SourceType.SEC_FILING,
            page=24,
            table_reference="Income Statement",
            url="https://sec.gov/...",
            date_accessed="2026-05-06",
        )
        row = c.to_table_row()
        assert "Amazon Q2 2024 10-Q" in row
        assert "p.24" in row
        assert "Income Statement" in row
        assert "2026-05-06" in row
        assert "[Link]" in row

    def test_database_citation(self):
        """Database-sourced citations include SQL reference."""
        c = Citation(
            source_name="general_ledger",
            source_type=SourceType.DATABASE_QUERY,
            query_sql="SELECT region, SUM(revenue) FROM quarterly_financials WHERE company='AMZN'",
            date_accessed="2026-05-06",
        )
        assert c.source_type == SourceType.DATABASE_QUERY


class TestValidateAnswerCitations:
    """Tests for citation validation of agent answers."""

    def test_well_cited_answer(self):
        """Answer with proper citations passes validation."""
        answer = """## Q2 Revenue Analysis

Revenue was $90.0B, up 9.1% from $82.5B.
Source: Amazon Q2 2024 10-Q, p.24, Income Statement

## Sources & References

### SEC Filings
| Source | Detail | Accessed | Link |
|--------|--------|----------|------|
| Amazon Q2 2024 10-Q | p.24 Income Statement | 2026-05-06 | [Link](https://sec.gov/...)
"""
        report = validate_answer_citations(answer)
        assert report.citation_count >= 1
        assert not report.has_unsourced
        assert report.is_complete

    def test_unsourced_answer_fails(self):
        """Answer without citations fails validation."""
        answer = "Revenue was $90.0 billion, up 11% from last year."
        report = validate_answer_citations(answer)
        assert report.citation_count == 0
        assert not report.is_complete

    def test_missing_sources_section(self):
        """Answer with inline citations but no Sources section is incomplete."""
        answer = """Revenue was $90.0B.
Source: Amazon Q2 2024 10-Q, p.24, Income Statement"""
        report = validate_answer_citations(answer)
        assert report.citation_count >= 1
        assert not report.is_complete  # Missing Sources & References section

    def test_unsourced_flag_detected(self):
        """[UNSOURCED] flags are detected."""
        answer = "Revenue was $90.0B. [UNSOURCED] No source available."
        report = validate_answer_citations(answer)
        assert report.has_unsourced
        assert not report.is_complete


class TestBuildSourcesSection:
    """Tests for Sources & References section builder."""

    def test_empty_citations(self):
        """No citations produces empty string."""
        result = build_sources_section([])
        assert result == ""

    def test_multiple_source_types(self):
        """Citations grouped by source type."""
        citations = [
            Citation(source_name="Apple Q2 2024 10-Q", source_type=SourceType.SEC_FILING, page=3),
            Citation(source_name="Apple Q2 2024 Earnings Release", source_type=SourceType.EARNINGS_RELEASE),
            Citation(source_name="Apple Q2 2024 Transcript", source_type=SourceType.EARNINGS_TRANSCRIPT),
        ]
        result = build_sources_section(citations)
        assert "### SEC Filings" in result
        assert "### Earnings Releases" in result
        assert "### Earnings Call Transcripts" in result

    def test_notes_included(self):
        """Methodology notes appear in Sources section."""
        citations = [Citation(source_name="test", source_type=SourceType.OTHER)]
        result = build_sources_section(citations, notes="Growth rate calculated as (Y2-Y1)/Y1")
        assert "### Methodology Notes" in result
        assert "Growth rate" in result


class TestAgentSystemPrompt:
    """Tests for the agent system prompt template."""

    def test_prompt_contains_all_sections(self):
        """System prompt includes all required sections."""
        assert "5 Phases" in AGENT_SYSTEM_PROMPT or "PLAN" in AGENT_SYSTEM_PROMPT
        assert "COLLECT" in AGENT_SYSTEM_PROMPT
        assert "ANALYZE" in AGENT_SYSTEM_PROMPT
        assert "VISUALIZE" in AGENT_SYSTEM_PROMPT
        assert "VERIFY" in AGENT_SYSTEM_PROMPT
        assert "Sources & References" in AGENT_SYSTEM_PROMPT
        assert "[UNSOURCED]" in AGENT_SYSTEM_PROMPT
        assert "Not financial advice" in AGENT_SYSTEM_PROMPT

    def test_prompt_contains_guardrails(self):
        """Guardrails are included in the prompt."""
        assert "NO automated transaction execution" in AGENT_SYSTEM_PROMPT
        assert "never invent figures" in AGENT_SYSTEM_PROMPT.lower()

    def test_citation_format_explained(self):
        """Citation format is documented."""
        assert "Source:" in AGENT_SYSTEM_PROMPT
        assert "p." in AGENT_SYSTEM_PROMPT
