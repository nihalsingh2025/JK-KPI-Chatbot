"""
Node: format_answer

Turns the query result metadata (never the raw rows) into a final natural
language answer. For results above the large-result threshold, the answer
points the user at the download rather than trying to summarize every row.
"""

import json
from langchain_openai import ChatOpenAI

from config import FAST_MODEL, OPENAI_API_KEY, LARGE_RESULT_ROW_THRESHOLD
from graph.state import AgentState
from tools.file_cache import export_csv

_llm = ChatOpenAI(model=FAST_MODEL, api_key=OPENAI_API_KEY, temperature=0)

SYSTEM_PROMPT = """You are a KPI dashboard assistant. Answer the user's
question using only the row_count, columns, and preview_rows given to you.
Never invent numbers not present in preview_rows.
If the granularity is MONTH and date is first day of month that means kpi are calculated for month that date is just a placeholder for that month, similar logic for YEAR granularity for first day of year.
Use the "large_result" flag to decide the answer style - do not judge
this yourself from row counts:
- If large_result is false: give a clean, direct summary of the preview
  rows. Do not mention downloading.
- If large_result is true: present the preview rows in sorted order as a
  quick snapshot, and mention that the full result can be downloaded for
  the detailed view."""


def format_answer(state: AgentState) -> AgentState:
    if state.get("execution_error"):
        state["final_answer"] = (
            f"The query could not be completed: {state['execution_error']}"
        )
        return state

    if state.get("row_count", 0) == 0:
        state["final_answer"] = "No data was found for that question."
        return state

    if state["row_count"] > LARGE_RESULT_ROW_THRESHOLD:
        export_csv(state["result_id"])

    context = {
        "user_question": state["user_query"],
        "row_count": state["row_count"],
        "columns": state["columns"],
        "preview_rows": state["preview_rows"],
        "large_result": state["row_count"] > LARGE_RESULT_ROW_THRESHOLD,
    }
    response = _llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(context, indent=2)},
    ])

    state["final_answer"] = response.content.strip()
    return state