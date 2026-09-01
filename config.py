"""
Central configuration for the KPI chatbot.
All tunable constants live here so nothing is hardcoded inside node logic.
"""

import os
from dotenv import load_dotenv
load_dotenv()

# --- Databricks REST API (wraps the existing script) ---
DATABRICKS_API_URL = "https://c7hzxcvdxh.execute-api.ap-south-1.amazonaws.com/query"
DATABRICKS_API_KEY = os.getenv("DATABRICKS_API_KEY", "")
DATABRICKS_ENGINE = "athena"
DATABRICKS_TABLE = "gold.gold"

# --- OpenAI ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CHAT_MODEL = "gpt-4o"
EMBEDDING_MODEL = "text-embedding-3-small"

# --- Result size routing ---
# Above this row count, results are cached to a file and only a preview
# plus a download link is shown to the user / passed to the LLM.
LARGE_RESULT_ROW_THRESHOLD = 50
PREVIEW_ROW_COUNT = 50

# --- KPI retrieval ---
KPI_REGISTRY_DIR = os.path.join(os.path.dirname(__file__), "kpi_registry")
TOP_K_KPI_MATCHES = 2

# --- File cache ---
RESULT_CACHE_DIR = os.path.join(os.path.dirname(__file__), ".result_cache")
os.makedirs(RESULT_CACHE_DIR, exist_ok=True)
