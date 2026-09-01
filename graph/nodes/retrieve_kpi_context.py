"""
Node: retrieve_kpi_context

Embeds the user's question, retrieves the top-k closest KPI registry
entries, and resolves any enum values (product_type/section/etc) mentioned
in the question. This context is what gets injected into the SQL
generation prompt in the next node.
"""

from graph.state import AgentState
from retrieval.embed_store import retriever
from retrieval.enum_values import relevant_enum_context


def retrieve_kpi_context(state: AgentState) -> AgentState:

    state["execution_error"] = None
    state["result_id"] = None
    state["row_count"] = None
    state["columns"] = None
    state["preview_rows"] = None
    state["download_path"] = None
    state["plot_spec"] = None

    query = state["user_query"]
    history = state.get("query_history") or []

    retrieved = retriever.retrieve(query)

    if history:
        last_family = history[-1].kpi_family
        if last_family and not any(e["kpi_family"] == last_family for e in retrieved):
            forced_entry = next((e for e in retriever.entries if e["kpi_family"] == last_family), None)
            if forced_entry:
                retrieved = [forced_entry] + retrieved

    state["kpi_context"] = retrieved
    state["current_kpi_family"] = retrieved[0]["kpi_family"] if retrieved else None
    state["enum_context"] = relevant_enum_context(query)

    return state
