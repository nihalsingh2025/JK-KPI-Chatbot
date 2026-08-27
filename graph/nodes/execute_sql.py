"""
Node: execute_sql

Runs the generated SQL against the Databricks REST API and caches the
result. The graph state only ever receives row_count / columns / a preview
- never the full result set - so downstream nodes and any further LLM
calls stay cheap regardless of how many rows came back.
"""

from graph.state import AgentState
from tools.databricks_api import run_query, DatabricksQueryError
from tools.file_cache import cache_result


def execute_sql(state: AgentState) -> AgentState:
    sql = state["generated_sql"]

    try:
        rows = run_query(sql)
    except DatabricksQueryError as exc:
        state["execution_error"] = str(exc)
        return state

    if not rows:
        state["row_count"] = 0
        state["columns"] = []
        state["preview_rows"] = []
        return state

    metadata = cache_result(rows)
    state["result_id"] = metadata["result_id"]
    state["row_count"] = metadata["row_count"]
    state["columns"] = metadata["columns"]
    state["preview_rows"] = metadata["preview_rows"]
    state["download_path"] = metadata["download_path"]

    return state
