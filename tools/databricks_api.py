"""
Thin wrapper around the existing Databricks REST API used to run SQL and
get results back as a list of row dicts. This is the only place that knows
about the HTTP details - if this project ever moves to a direct Databricks
SQL connector, only this file needs to change.
"""

import requests

from config import DATABRICKS_API_URL, DATABRICKS_API_KEY, DATABRICKS_ENGINE


class DatabricksQueryError(Exception):
    pass


def run_query(sql: str) -> list:
    """Execute a SQL string against the gold layer and return rows as dicts."""
    payload = {"engine": DATABRICKS_ENGINE, "sql": sql}
    headers = {
        "x-api-key": DATABRICKS_API_KEY,
        "Content-Type": "application/json",
    }

    response = requests.post(DATABRICKS_API_URL, json=payload, headers=headers)

    if response.status_code != 200:
        raise DatabricksQueryError(
            f"Query failed with status {response.status_code}: {response.text}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise DatabricksQueryError("Invalid JSON response from Databricks API") from exc

    rows = data.get("rows") or data.get("data") or data.get("results")
    if rows is None:
        raise DatabricksQueryError("No tabular data found in API response")

    return rows
