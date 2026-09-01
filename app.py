"""
Streamlit entrypoint. Renders a simple, professional chat panel meant to be
embedded inside the JS Tyres KPI dashboard. Each user message runs the
LangGraph agent once and displays the answer, an optional chart, and an
optional download button for large results.
"""

import os
import streamlit as st
import uuid

from graph.build_graph import build_graph
from tools.file_cache import export_csv
from config import LARGE_RESULT_ROW_THRESHOLD
from tools.file_cache import load_result
from tools.plotting import render

# os.environ["LANGSMITH_TRACING"] = "true"
# os.environ["LANGSMITH_API_KEY"] = st.secrets["LANGSMITH_API_KEY"]
# os.environ["LANGSMITH_PROJECT"] = "kpi_chatbot"

st.set_page_config(page_title="KPI Assistant", layout="centered")

if "graph" not in st.session_state:
    st.session_state.graph = build_graph()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

st.title("JK KPI Assistant")
st.caption("Ask questions about production, OEE, and breakdown KPIs.")

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_query = st.chat_input("Ask a question about your KPIs")

if user_query:
    st.session_state.chat_history.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.write(user_query)

    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    with st.spinner("Please wait while I process your query..."):
        result = st.session_state.graph.invoke({"user_query": user_query},config=config)

    with st.chat_message("assistant"):
        st.write(result.get("final_answer", "Something went wrong."))

        plot_spec = result.get("plot_spec")
        if result.get("wants_plot") and plot_spec:
            df = load_result(result["result_id"])
            valid_columns = set(df.columns)

            x_ok = plot_spec.get("x") in valid_columns
            y_ok = plot_spec.get("y") in valid_columns
            group_by = plot_spec.get("group_by")
            group_by_ok = group_by is None or group_by in valid_columns

            if x_ok and y_ok and group_by_ok:
                kwargs = {k: v for k, v in plot_spec.items() if k != "chart_type" and v is not None}
                figure = render(plot_spec["chart_type"], df, **kwargs)
                st.plotly_chart(figure, use_container_width=True)
            else:
                st.info("A chart could not be generated for this result.")

        row_count = result.get("row_count") or 0
        if row_count > LARGE_RESULT_ROW_THRESHOLD and result.get("result_id"):
            csv_path = export_csv(result["result_id"])
            with open(csv_path, "rb") as f:
                st.download_button(
                    "Download full result (CSV)",
                    data=f,
                    file_name=f"kpi_result_{result['result_id']}.csv",
                    mime="text/csv",
                )

    st.session_state.chat_history.append(
        {"role": "assistant", "content": result.get("final_answer", "")}
    )
