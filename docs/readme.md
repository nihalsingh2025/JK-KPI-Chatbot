# README - KPI Chatbot Codebase

This document explains what each file and function does and how they
connect. Read `tech.md` first for the design rationale; this file is the
map of the actual code.

## Folder structure

```
kpi_chatbot/
├── app.py
├── config.py
├── requirements.txt
├── tech.md
├── readme.md
├── graph/
│   ├── state.py
│   ├── build_graph.py
│   └── nodes/
│       ├── retrieve_kpi_context.py
│       ├── generate_sql.py
│       ├── execute_sql.py
│       ├── format_answer.py
│       └── plot.py
├── kpi_registry/
│   ├── production.yaml
│   ├── oee.yaml
│   └── breakdown.yaml
├── retrieval/
│   ├── embed_store.py
│   └── enum_values.py
└── tools/
    ├── databricks_api.py
    ├── file_cache.py
    └── plotting.py
```

## Execution flow (one user question)

1. `../app.py` collects the question from the Streamlit chat input and calls
   `graph.invoke({"user_query": question})`.
2. The compiled LangGraph (built by `../graph/build_graph.py`) runs the
   nodes in order:
   `retrieve_kpi_context -> generate_sql -> execute_sql -> format_answer`,
   then conditionally `-> plot` if the question asked for a chart.
3. `../app.py` reads the final state and renders the answer text, an
   optional chart, and an optional CSV download button.

Every node takes an `AgentState` dict, mutates/adds keys, and returns it.
No node imports another node directly - they only communicate through the
state dict, so nodes can be reordered, tested, or replaced independently.

## config.py

Holds every constant used elsewhere: API URL/keys, model names, the
large-result row threshold, preview row count, and the result cache
directory. Nothing else in the codebase should hardcode these values.

## graph/state.py

Defines `AgentState`, the `TypedDict` passed between all nodes. See
`tech.md` section 3 for the "no raw rows in state" principle this
enforces. Fields are grouped by phase: input, retrieval, SQL
generation/execution, results, plotting, final output.

## graph/build_graph.py

- `_wants_plot(state)` - conditional edge function; keyword-checks the
  user question for chart-intent words and routes to either the `plot`
  node or straight to `END`.
- `build_graph()` - constructs the `StateGraph`, registers all five
  nodes, wires the linear edges plus the one conditional edge, and
  returns the compiled graph that `../app.py` calls `.invoke()` on.

## graph/nodes/retrieve_kpi_context.py

- `retrieve_kpi_context(state)` - calls `retriever.retrieve(query)` from
  `../retrieval/embed_store.py` to get the top-k matching KPI registry
  entries, and `relevant_enum_context(query)` from
  `../retrieval/enum_values.py` to get any exact column values mentioned in
  the question. Writes both into `state["kpi_context"]` and
  `state["enum_context"]`.

## graph/nodes/generate_sql.py

- `_build_user_prompt(state)` - flattens the retrieved KPI context and
  enum context into the text block sent to the model.
- `generate_sql(state)` - sends `SYSTEM_PROMPT` (the SQL-writing rules)
  plus the built user prompt to `ChatOpenAI` and stores the raw SQL
  string in `state["generated_sql"]`.

## graph/nodes/execute_sql.py

- `execute_sql(state)` - calls `tools/databricks_api.run_query()` with
  the generated SQL. On success, passes the rows to
  `tools/file_cache.cache_result()` and copies the returned metadata
  (`result_id`, `row_count`, `columns`, `preview_rows`, `download_path`)
  into state. On failure, stores the error in
  `state["execution_error"]` instead of raising, so the graph can still
  reach `format_answer` and report the problem to the user.

## graph/nodes/format_answer.py

- `format_answer(state)` - if there was an execution error or zero rows,
  returns a direct message without calling the LLM. Otherwise, if the
  result is above `LARGE_RESULT_ROW_THRESHOLD`, pre-exports the CSV (so
  it is ready before the user even asks) and asks `ChatOpenAI` to
  summarize using only `row_count`, `columns`, and `preview_rows` -
  never the full result set.

## graph/nodes/plot.py

- `_choose_plot_spec(state)` - asks `ChatOpenAI` to return a JSON
  `plot_spec` (`chart_type`, `x`, `y`, `group_by`) based on the schema
  and preview rows only.
- `plot(state)` - loads the full cached dataframe via
  `tools/file_cache.load_result()`, calls `tools/plotting.render()` with
  the chosen spec, and stores the resulting Plotly figure object in
  `state["_figure"]` for `../app.py` to display. Does nothing if there is no
  cached result to plot.

## kpi_registry/*.yaml

One file per KPI family (`production.yaml`, `oee.yaml`,
`breakdown.yaml`). Each has the same shape: `kpi_family`, `kpi_names`,
`description`, `variant_selection_rules` (which of several KPI name
variants to use, e.g. `Production` vs `Production_m`),
`default_select_columns`, `gotchas` (known correctness pitfalls in the
data), and `example_questions` (few-shot question/SQL pairs). This is
plain data, loaded and embedded by `../retrieval/embed_store.py` - adding a
new KPI family means adding a new YAML file here, nothing else.

## retrieval/embed_store.py

- `_load_registry()` - reads every YAML file in `../kpi_registry` into a
  list of dicts.
- `_embed_text(text)` - calls the OpenAI embeddings API for a string.
- `_doc_text(entry)` - flattens one registry entry's description and
  example questions into a single string to embed.
- `KpiRetriever` - holds the registry entries and their embeddings in
  memory; `.build()` embeds everything once, `.retrieve(query, top_k)`
  embeds the incoming question and returns the closest entries by cosine
  similarity.
- `retriever` - a module-level `KpiRetriever` instance, built lazily on
  first use, so the embedding index is only computed once per process.

## retrieval/enum_values.py

Static Python lists/dicts of known column values (`PRODUCT_TYPES`,
`SECTIONS`, `SUB_SECTIONS`, `CATEGORIES`, `GRANULARITIES`).

- `relevant_enum_context(user_query)` - keyword-matches the question
  against these lists and returns only the groups actually mentioned, so
  the SQL generation prompt gets exact spellings without being padded
  with irrelevant enum lists every time.

## tools/databricks_api.py

- `run_query(sql)` - posts the SQL to the existing REST API endpoint
  using the same payload shape as the original extraction script, parses
  the JSON response, and returns the row list. Raises
  `DatabricksQueryError` on a non-200 status, invalid JSON, or a missing
  rows/data/results key, so callers can catch one specific exception
  type.

## tools/file_cache.py

- `cache_result(rows)` - converts rows to a pandas DataFrame, writes it
  to a parquet file under `../.result_cache` named by a new UUID
  (`result_id`), and returns metadata (`result_id`, `row_count`,
  `columns`, `preview_rows`, `download_path`).
- `load_result(result_id)` - reads a cached parquet file back into a
  DataFrame, used by the plot node.
- `export_csv(result_id)` - converts a cached result to CSV for the
  Streamlit download button.

## tools/plotting.py

- `bar_chart`, `line_chart`, `pie_chart` - thin wrappers around Plotly
  Express that take a DataFrame and column names.
- `CHART_FUNCTIONS` - maps chart type strings to the functions above.
- `render(chart_type, df, **kwargs)` - dispatch function used by
  `../graph/nodes/plot.py`; this is the only function outside this file
  that needs to know charts exist.

## app.py

The Streamlit UI. Builds the graph once per session
(`st.session_state.graph`), keeps chat history in
`st.session_state.chat_history`, and on each new question calls
`graph.invoke()`, then renders the returned `final_answer`, an optional
Plotly figure (`result["_figure"]`), and an optional CSV download button
when `row_count` exceeds the large-result threshold.

## Environment variables required

- `OPENAI_API_KEY` - used by `generate_sql.py`, `format_answer.py`,
  `plot.py`, and `embed_store.py`.
- `DATABRICKS_API_KEY` - used by `../tools/databricks_api.py`.

## Running it

```
pip install -r requirements.txt
export OPENAI_API_KEY=...
export DATABRICKS_API_KEY=...
streamlit run app.py
```
