"""
Node: format_answer

Turns the query result metadata (never the raw rows) into a final natural
language answer. For results above the large-result threshold, the answer
points the user at the download rather than trying to summarize every row.
"""

import json
from openai import OpenAI

from config import CHAT_MODEL, OPENAI_API_KEY, LARGE_RESULT_ROW_THRESHOLD
from graph.state import AgentState
from tools.file_cache import export_csv

_client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """You are a KPI dashboard assistant. Write a short,
professional answer to the user's question using only the row count,
columns, and preview rows given to you. Do not invent numbers that are not
present in the preview. If the preview does not fully answer the question
because there are many rows, summarize what is available and mention that
the full result is downloadable."""


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

    response = _client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context, indent=2)},
        ],
        temperature=0,
    )

    state["final_answer"] = response.choices[0].message.content.strip()
    return state
