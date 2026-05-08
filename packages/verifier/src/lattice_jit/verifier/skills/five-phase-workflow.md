# Five-Phase Financial Analysis Workflow

> Adopted from: Anthropic financial-services `earnings-analysis/SKILL.md`
> License: Apache 2.0 (adapted)
> Purpose: Mandatory phase-structured workflow for the Finance Agent Model

---

## Overview

Every financial analysis query MUST follow this 5-phase structure:

```
PLAN → COLLECT → ANALYZE → VISUALIZE → VERIFY
```

Each phase is a tool-call boundary. The agent must not skip phases or jump directly to output.

---

## Phase 1: PLAN (Data Source Identification)

**Goal:** Identify all data sources needed before executing any tool.

**What to output:**
```markdown
**Phase 1 — PLAN:** I need the following data:
1. {DATA_POINT} → {TOOL_NAME}({PARAMETERS})
2. {DATA_POINT} → {TOOL_NAME}({PARAMETERS})
...
```

**Checklist:**
- [ ] At least one data source identified
- [ ] Each source mapped to a specific tool
- [ ] Parameters specified (company, year, database, table)
- [ ] No tool calls made yet — plan only

**Example:**
```markdown
**Phase 1 — PLAN:** I need:
1. Q2 2024 revenue data → query_database("SELECT * FROM quarterly_revenue WHERE company='AMZN' AND quarter=2 AND year=2024", "general_ledger")
2. Q2 2023 comparison data → query_database("SELECT * FROM quarterly_revenue WHERE company='AMZN' AND quarter=2 AND year=2023", "general_ledger")  
3. Consensus estimates → search_documents("Amazon Q2 2024 consensus revenue estimates earnings release", company="Amazon")
4. Earnings call commentary → search_documents("Amazon Q2 2024 earnings call transcript revenue drivers", company="Amazon", source_type="transcript")
```

---

## Phase 2: COLLECT (Data Retrieval)

**Goal:** Execute all planned tool calls in parallel where possible.

**What to output:**
```markdown
**Phase 2 — COLLECT:** Retrieving data...

<tool_call>
{tool_name}({parameters})
</tool_call>
```

**Checklist:**
- [ ] All Phase 1 data sources retrieved
- [ ] Tool calls return valid data (not empty, not error)
- [ ] Retry on transient failures (max 2 attempts)
- [ ] If a source is unavailable, note it explicitly

**Example:**
```markdown
**Phase 2 — COLLECT:** Retrieving quarterly revenue data...

<tool_call>
query_database({"sql": "SELECT region, year, quarter, SUM(revenue) as rev FROM quarterly_financials WHERE company='AMZN' AND quarter=2 AND year IN (2023,2024) GROUP BY region, year, quarter", "database": "general_ledger"})
</tool_call>
```

---

## Phase 3: ANALYZE (Computation & Analysis)

**Goal:** Compute financial metrics, identify trends, compare periods.

**What to output:**
```markdown
**Phase 3 — ANALYZE:** Computing financial metrics...

<tool_call>
analyze({"data": [...], "method": "yoy_growth"})
</tool_call>
```

**Checklist:**
- [ ] Growth rates computed (YoY, QoQ where applicable)
- [ ] Key ratios calculated (margins, coverage, turnover)
- [ ] Trends identified (direction, magnitude, significance)
- [ ] Discrepancies flagged (10-K vs SQL ledger mismatch)

**Required analysis methods:**
| Method | Formula | Use case |
|--------|---------|----------|
| `yoy_growth` | `(current - previous) / previous * 100` | Annual comparison |
| `qoq_growth` | `(current_q - prev_q) / prev_q * 100` | Sequential quarterly |
| `margin` | `(metric / revenue) * 100` | Gross, operating, net margins |
| `ratio` | Varies (current ratio, quick ratio, D/E) | Financial health |
| `trend` | Linear regression over N periods | Directional analysis |
| `variance` | `actual - budget / forecast` | Budget vs actual |

**Example:**
```markdown
**Phase 3 — ANALYZE:** Computing growth rates and margins...

<tool_call>
analyze({"data": [["North America", 2023, 82541], ["North America", 2024, 90033], ["International", 2023, 29697], ["International", 2024, 31662]], "method": "yoy_growth"})
</tool_call>
```

---

## Phase 4: VISUALIZE (Chart Generation)

**Goal:** Generate charts when the user requests them or when data comparison benefits from visualization.

**TRIGGER CONDITIONS — Always visualize when:**
- User explicitly asks for a chart/graph/plot/visualization
- Data has 2+ categories × 2+ time periods (comparison)
- Trend analysis over 4+ periods
- Regional/segment breakdown

**What to output:**
```markdown
**Phase 4 — VISUALIZE:** Generating chart...

<tool_call>
visualize({"data": [...], "chart_type": "{type}", "title": "{title}"})
</tool_call>
```

**Chart type selection:**
| Data pattern | Chart type |
|-------------|------------|
| Compare values across categories | `bar` |
| Show trend over time | `line` |
| Compare categories × time | `grouped_bar` |
| Show distribution | `histogram` |
| Show proportion of total | `pie` |
| Show relationship between variables | `scatter` |
| Stack composition over time | `stacked_bar` |
| Correlation matrix | `heatmap` |

**Required chart metadata:**
- Title with company + period + metric
- X-axis label
- Y-axis label
- Legend (if grouped)
- Data source annotation

**Example:**
```markdown
**Phase 4 — VISUALIZE:** Creating comparison chart...

<tool_call>
visualize({"data": [["North America", 2023, 82541], ["North America", 2024, 90033], ["International", 2023, 29697], ["International", 2024, 31662]], "chart_type": "grouped_bar", "x": "region", "y": "rev", "group": "year", "title": "Amazon Q2 Revenue by Region (2023 vs 2024)", "x_label": "Region", "y_label": "Revenue ($M)", "colors": ["#1f77b4", "#ff7f0e"]})
</tool_call>
```

---

## Phase 5: VERIFY (Quality Check)

**Goal:** Cross-validate results, ensure citation completeness, flag issues.

**What to output:**
```markdown
**Phase 5 — VERIFY:** Cross-validating results...

- [ ] All numbers cross-referenced with source documents
- [ ] Calculations double-checked
- [ ] Sources cited for every data point
- [ ] Discrepancies flagged (if any)
- [ ] Final answer ready
```

**Checklist:**
- [ ] Every numeric fact has: (source, page, table/row)
- [ ] Calculations shown with explicit formulas
- [ ] Cross-source comparison: SEC filing vs SQL ledger
- [ ] If chart generated: data provenance verified
- [ ] Sources & References section complete
- [ ] `[UNSOURCED]` flag not present in final output
- [ ] Disclaimer footer included

**Verification matrix:**

| What | How to verify |
|------|---------------|
| Revenue number | Compare 10-K vs SQL ledger vs earnings release |
| Growth rate | Recompute from raw numbers |
| Chart data | Trace chart values back to source query |
| Source integrity | Verify SEC EDGAR links are accessible |
| Citation format | Check: source name + page + table + link |

---

## Phase Transition Rules

1. **Never skip phases.** Every query goes through all 5.
2. **Plan before Collect.** No tool calls without a plan.
3. **Collect before Analyze.** No analysis without data.
4. **Analyze before Visualize.** No chart without computed metrics.
5. **Verify before Output.** No answer without verification checklist.

**Minimum phases by query type:**

| Query type | Required phases |
|------------|----------------|
| "What was Q2 revenue?" | Plan → Collect → Analyze → Verify |
| "Show Q2 revenue growth chart" | Plan → Collect → Analyze → Visualize → Verify |
| "Compare Q2 to Q2 last year" | Plan → Collect → Analyze → Verify |
| "Forecast Q3 revenue" | Plan → Collect → Analyze (forecast) → Verify |
| "Full earnings analysis with charts" | Plan → Collect → Analyze → Visualize → Verify |

---

## Anti-Patterns (DO NOT DO)

❌ Jumping directly to tool calls without a plan
❌ Skipping verification phase
❌ Answering from training data without collecting fresh data
❌ Including `[UNSOURCED]` data points in final answer
❌ Generating charts without labeling axes or citing data source
❌ Omitting the Sources & References section
