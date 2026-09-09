"""
Wires all nodes into a single LangGraph StateGraph. This is the only file
that defines control flow - individual nodes stay simple, single-purpose
functions with no knowledge of what runs before or after them.

Flow:
    retrieve_kpi_context -> generate_sql -> execute_sql -> format_answer
        -> [plot node, only if the question asks for a chart] -> END
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

from graph.state import AgentState
from graph.nodes.retrieve_kpi_context import retrieve_kpi_context
from graph.nodes.generate_sql import generate_sql
from graph.nodes.execute_sql import execute_sql
from graph.nodes.format_answer import format_answer
from graph.nodes.plot import plot
from graph.nodes.detect_plot_intent import detect_plot_intent


#A full LLM call just to decide "should I plot" would be wasteful for a binary decision like this.
def _route_after_format_answer(state: AgentState) -> str:
    return "plot" if state.get("wants_plot") else "end"

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("retrieve_kpi_context", retrieve_kpi_context)
    graph.add_node("generate_sql", generate_sql)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("format_answer", format_answer)
    graph.add_node("detect_plot_intent", detect_plot_intent)
    graph.add_node("plot", plot)

    graph.set_entry_point("retrieve_kpi_context")
    graph.add_edge("retrieve_kpi_context", "generate_sql")
    graph.add_edge("generate_sql", "execute_sql")
    graph.add_edge("execute_sql", "format_answer")

    graph.add_edge("format_answer", "detect_plot_intent")

    graph.add_conditional_edges(
        "detect_plot_intent",
        _route_after_format_answer,
        {"plot": "plot", "end": END},
    )
    graph.add_edge("plot", END)

    checkpointer = InMemorySaver()
    return graph.compile(checkpointer=checkpointer)
