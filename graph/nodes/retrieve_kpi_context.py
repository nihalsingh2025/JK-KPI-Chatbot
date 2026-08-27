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
    query = state["user_query"]

    state["kpi_context"] = retriever.retrieve(query)
    state["enum_context"] = relevant_enum_context(query)

    return state
