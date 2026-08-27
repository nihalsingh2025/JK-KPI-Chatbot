# JS Tyres KPI Chatbot - Technical Design (v1)

## 1. Purpose

A conversational assistant embedded in the JS Tyres KPI dashboard that
answers questions over a precalculated KPI gold layer table. It does not
need to compute or aggregate raw manufacturing data - the gold layer
already holds calculated KPI values - so the assistant's job is
natural-language-to-SQL translation, plus comparison, visualization, and
report generation on top of the returned data.

## 2. Data source

- Table: `jk-infiniti-datalake`.gold.gold_bi (referred to as `gold.gold`
  in the original extraction script).
- Access: existing REST API (Athena engine, `x-api-key` auth), not a
  direct Databricks SQL connector. All HTTP details are isolated in
  `../tools/databricks_api.py` so this can be swapped later without touching
  the rest of the system.
- Column semantics (granularity, department, section/sub_section,
  product_type, itemcode, category, unit_of_measurement, actual_value,
  drill-down columns) are documented per KPI family in `../kpi_registry`.

## 3. Architecture overview

```
Streamlit UI (chat panel)
        |
   LangGraph orchestrator
        |
   retrieve_kpi_context -> generate_sql -> execute_sql -> format_answer
                                                                |
                                              (conditional: explicit
                                               chart/graph/compare ask)
                                                                |
                                                              plot -> END
```

LangGraph was chosen over a plain LangChain ReAct agent because this
workflow needs explicit, auditable control flow (always attach KPI
context before generating SQL, always route based on result size, only
plot on explicit request) rather than letting the LLM freely decide when
to call tools. LangChain components (ChatOpenAI client, prompt patterns)
are still used inside individual nodes.

Guiding principle: **the LLM never sees raw result rows beyond a small
preview.** Every tool that returns tabular data returns
`{row_count, columns, preview_rows, result_id}`; the full dataframe lives
server-side in a cache keyed by `result_id`.

## 4. KPI registry (modular prompt context)

Rather than one long static prompt covering every KPI, each KPI family
gets its own YAML file under `../kpi_registry` containing: description,
variant selection rules, default columns to select, known gotchas, and a
few example question/SQL pairs.

At query time:
1. The user's question is embedded (OpenAI embeddings).
2. The top-k closest KPI registry entries are retrieved via cosine
   similarity (`../retrieval/embed_store.py`).
3. Only those entries are injected into the SQL generation prompt.

This keeps token usage proportional to the question, avoids one giant
prompt that grows brittle as KPIs are added, and lets new KPI families be
added by dropping in a new YAML file - no code changes needed.

A keyword/regex pre-filter fused with embedding retrieval was considered
but deferred for v1: with the current registry size, pure embedding
retrieval should have enough recall. Revisit if testing shows real
retrieval misses.

Known exact string values (product_type, section, sub_section, category)
are kept in a separate static index (`../retrieval/enum_values.py`) and
included in the prompt only when relevant, so SQL generation uses correct
spellings instead of guessing.

## 5. Large result handling

- `execute_sql` runs the generated SQL, caches the full result to a
  parquet file on disk (`../tools/file_cache.py`), and returns only
  `row_count`, `columns`, and a small preview to the graph state.
- `format_answer` answers from that metadata only. If `row_count` exceeds
  `LARGE_RESULT_ROW_THRESHOLD` (200, configurable in `../config.py`), the
  result is exported to CSV and the Streamlit UI shows a real download
  button - the LLM is only told a download is available, it never
  receives the full data.

## 6. Date range handling

- A date range without an explicit "total"/"overall" ask returns per-day
  rows (`granularity = 'day'`, `date BETWEEN ...`).
- A date range with an explicit total/overall ask aggregates with
  `SUM(actual_value)`, drops `date` from the SELECT, and groups by
  whatever other dimensions (machine, itemcode, etc.) are relevant.
- This rule is encoded directly in each KPI registry file's `gotchas`
  section, not hardcoded in Python, so it can be refined per KPI family.

## 7. Ambiguity handling

- If a question does not specify a machine/sku/section breakdown, the
  KPI variant defaults to the overall (non-broken-down) version rather
  than asking a clarifying question.
- Conversation is currently self-contained per question - no multi-turn
  memory of prior filters yet. Follow-up questions must restate context.
  (Flagged as a v2 candidate.)

## 8. SQL guardrails

Not implemented in v1 by decision - the REST API layer already
constrains what can be executed, and the use case is read-only /
SELECT-only by construction of the KPI registry prompts. If needed later
(e.g. before wider rollout), a `validate_sql` node can be inserted
between `generate_sql` and `execute_sql` without touching any other node:
statement-shape check (single SELECT only), table/column allow-list,
row/time limits, and an audit log of generated SQL per question.

## 9. Plotting

- The plot node only runs when the question contains explicit visual
  intent (graph, chart, plot, visual, compare, comparison) - checked with
  a simple keyword match, not an LLM call, since it is a binary decision.
- Supported chart types: bar, double bar (grouped bar), line, double
  line (multi-series), pie.
- The LLM only chooses a `plot_spec` (`chart_type`, `x`, `y`, `group_by`)
  from the schema and preview rows; the chart itself is rendered by fixed
  Python functions (`../tools/plotting.py`), never LLM-authored code.
- Plotly is used as the default charting library for v1; the final choice
  is still open for a later discussion and can be swapped by editing only
  `../tools/plotting.py`.

## 10. Column selection

Each KPI registry entry lists `default_select_columns`, so generated
queries select only the columns relevant to that KPI family instead of
`SELECT *`, dropping unused metadata columns (`logbook_id`, `eqname`,
`arbpl`, `equnr`, etc.) except where a KPI specifically needs them (e.g.
`remarks` for Breakdown).

## 11. Folder structure

See `readme.md` for a full function-by-function breakdown of every file.

## 12. Open items / v2 candidates

- SQL validation/guardrail node.
- Multi-turn conversational memory (carrying filters across follow-ups).
- Hybrid keyword + embedding KPI retrieval, if embedding-only retrieval
  shows gaps in testing.
- Final chart library decision (currently Plotly by default).
- Additional KPI registry files beyond Production, OEE, and Breakdown as
  more KPI families are documented.
