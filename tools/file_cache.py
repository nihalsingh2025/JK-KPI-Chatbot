"""
Caches query results server-side so the LLM never has to see, or pay
tokens for, raw rows. Every executed query gets a result_id; the node
layer only passes row_count / columns / a small preview back into the
graph state. The full dataframe is retrieved later by result_id when the
user wants to download it or plot it.
"""

import os
import uuid
import pandas as pd
import glob

from config import RESULT_CACHE_DIR, PREVIEW_ROW_COUNT


MAX_CACHED_RESULTS = 5

def cache_result(rows: list) -> dict:
    """
    Store rows as a dataframe on disk and return metadata describing it.

    Returns a dict with: result_id, row_count, columns, preview_rows,
    download_path.
    """
    df = pd.DataFrame(rows)
    result_id = str(uuid.uuid4())
    path = os.path.join(RESULT_CACHE_DIR, f"{result_id}.parquet")
    df.to_parquet(path, index=False)

    _enforce_cache_limit()

    return {
        "result_id": result_id,
        "row_count": len(df),
        "columns": list(df.columns),
        "preview_rows": df.head(PREVIEW_ROW_COUNT).to_dict(orient="records"),
        "download_path": path,
    }

def _enforce_cache_limit():
    """Keep only the MAX_CACHED_RESULTS most recently created results on disk."""
    parquet_files = sorted(
        glob.glob(os.path.join(RESULT_CACHE_DIR, "*.parquet")),
        key=os.path.getmtime,
        reverse=True,
    )
    for old_file in parquet_files[MAX_CACHED_RESULTS:]:
        result_id = os.path.splitext(os.path.basename(old_file))[0]
        os.remove(old_file)
        csv_file = os.path.join(RESULT_CACHE_DIR, f"{result_id}.csv")
        if os.path.exists(csv_file):
            os.remove(csv_file)

def load_result(result_id: str) -> pd.DataFrame:
    """Load a previously cached result back into a dataframe."""
    path = os.path.join(RESULT_CACHE_DIR, f"{result_id}.parquet")
    return pd.read_parquet(path)


def export_csv(result_id: str) -> str:
    """Convert a cached result to CSV for the Streamlit download button."""
    df = load_result(result_id)
    csv_path = os.path.join(RESULT_CACHE_DIR, f"{result_id}.csv")
    df.to_csv(csv_path, index=False)
    return csv_path
