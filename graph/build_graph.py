"""
Wires all nodes into a single LangGraph StateGraph. This is the only file
that defines control flow - individual nodes stay simple, single-purpose
functions with no knowledge of what runs before or after them.

Flow:
    retrieve_kpi_context -> generate_sql -> execute_sql -> format_answer
        -> [plot node, only if the question asks for a chart] -> END
"""

from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes.retrieve_kpi_context import retrieve_kpi_context
from graph.nodes.generate_sql import generate_sql
from graph.nodes.execute_sql import execute_sql
from graph.nodes.format_answer import format_answer
from graph.nodes.plot import plot


# Keyword check used to decide whether the plot node should run at all.
# Kept intentionally simple - a full LLM call just to decide "should I
# plot" would be wasteful for a binary decision like this.
PLOT_KEYWORDS = ["graph", "chart", "plot", "visual","visualize", "compare", "comparison","trend"]


def _wants_plot(state: AgentState) -> str:
    """Conditional edge: route to the plot node only on explicit visual asks."""
    query_lower = state["user_query"].lower()
    if any(keyword in query_lower for keyword in PLOT_KEYWORDS):
        return "plot"
    return "end"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("retrieve_kpi_context", retrieve_kpi_context)
    graph.add_node("generate_sql", generate_sql)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("format_answer", format_answer)
    graph.add_node("plot", plot)

    graph.set_entry_point("retrieve_kpi_context")
    graph.add_edge("retrieve_kpi_context", "generate_sql")
    graph.add_edge("generate_sql", "execute_sql")
    graph.add_edge("execute_sql", "format_answer")

    graph.add_conditional_edges(
        "format_answer",
        _wants_plot,
        {"plot": "plot", "end": END},
    )
    graph.add_edge("plot", END)

    return graph.compile()
