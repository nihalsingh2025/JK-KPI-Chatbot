"""
Node: generate_sql

Builds a prompt from the retrieved KPI context plus enum context and asks
ChatOpenAI to produce a single Databricks SQL SELECT statement. Only the
retrieved fragments (not the full KPI registry) go into the prompt, keeping
token usage proportional to what the question actually needs.
"""

import json
from pydantic import  BaseModel
from langchain_openai import ChatOpenAI
from config import CHAT_MODEL, OPENAI_API_KEY, DATABRICKS_TABLE
from graph.state import AgentState
from datetime import date

class SQLQuery(BaseModel):
    sql: str

_llm = ChatOpenAI(model=CHAT_MODEL, api_key=OPENAI_API_KEY, temperature=0).with_structured_output(SQLQuery)

SYSTEM_PROMPT = f"""You are a SQL generation assistant for a tyre
manufacturing KPI dashboard. You write a single Databricks SQL SELECT
statement against the table {DATABRICKS_TABLE}.

Rules:
- Always use lower() when comparing string columns to static values.
- Only select the columns listed under default_select_columns for the
  matched KPI family, plus any columns needed to answer the question.
- Follow the variant_selection_rules and gotchas given in the KPI context
  exactly - they encode known correctness issues in this data.
- If the question implies a date range without asking for a total, return
  per-day rows (granularity = 'day'). If it asks for a total/overall figure
  across a range, use SUM(actual_value) and drop 'date' from the SELECT and
  GROUP BY the remaining relevant dimensions instead.
- Default to the overall (non machine/sku-specific) KPI variant if the
  question does not specify a breakdown.
- Always sort results with ORDER BY date ASC by default, unless the user explicitly asks for a different sort order (e.g. "highest first", "sort by machine").
- Always write date literals as Date 'YYYY-MM-DD', e.g. date = Date '2026-08-16', not a bare string.
- If the user gives a relative date reference without a year (e.g. "this month", "last month", "this year", "today"), resolve it using the CURRENT_DATE provided below - do not assume any other year.
"""


def _build_user_prompt(state: AgentState) -> str:
    parts = [f"CURRENT_DATE: {date.today().isoformat()}",f"User question: {state['user_query']}", "", "Matched KPI context:"]
    for entry in state.get("kpi_context", []):
        parts.append(json.dumps(entry, indent=2))

    enum_context = state.get("enum_context") or {}
    if enum_context:
        parts.append("\nRelevant known column values:")
        parts.append(json.dumps(enum_context, indent=2))

    return "\n".join(parts)


def generate_sql(state: AgentState) -> AgentState:
    user_prompt = _build_user_prompt(state)

    result = _llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ])

    state["generated_sql"] = result.sql.strip()
    return state
