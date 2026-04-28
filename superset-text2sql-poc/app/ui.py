import urllib.parse
import streamlit as st
from app.config import settings
from app.database import table_exists
from app.metadata import get_schema_metadata, build_metadata_context
from app.metrics_catalog import load_metrics_catalog
from app.prompt_builder import build_system_prompt, build_user_prompt
from app.llm_client import generate_sql
from app.sql_validator import validate_sql

EXAMPLE_QUESTIONS = [
    "Show me the top 10 lines with the highest average delay in the last 30 days.",
    "Calculate punctuality rate by line for the current month.",
    "Show daily passenger count trend for the last 60 days.",
    "List vehicles with the highest number of critical anomalies.",
    "Compare average delay between bus and tram lines.",
    "Show the number of diagnostic alarms by severity in the last 30 days.",
    "Compare passenger boardings by transport mode for the last 60 days.",
]


def main():
    st.set_page_config(
        page_title="Text-to-SQL PoC — Superset AI SQL Lab",
        page_icon="🚌",
        layout="wide",
    )

    st.title("Text-to-SQL PoC — AI-Assisted SQL Lab")
    st.markdown(
        "Generate SQL queries from natural language for public transport analytics. "
        "Powered by an LLM via **OpenRouter**. Designed to be used alongside **Apache Superset SQL Lab**."
    )

    st.warning(
        "⚠️ **The generated SQL is not executed automatically. "
        "Please review it carefully before copying it into Apache Superset SQL Lab.**"
    )

    # Config check
    config_errors = settings.validate()
    if config_errors:
        st.error(f"Configuration error: {config_errors[0]}")
        st.info("Set `LLM_API_KEY` in your `.env` file and restart the app.")
        st.stop()

    # DB check
    if not table_exists("lines"):
        st.error("Demo database not found or not seeded. Run: `python -m app.seed_demo_data`")
        st.stop()

    # Sidebar: metadata
    with st.sidebar:
        st.header("Available Data")
        schema = get_schema_metadata()
        for table_name, info in schema.items():
            with st.expander(f"📋 {table_name}"):
                st.markdown(f"*{info['description']}*")
                for col in info["columns"]:
                    st.markdown(f"- `{col['name']}` ({col['type']})")

        st.header("Certified Metrics")
        metrics = load_metrics_catalog()
        for metric_name, info in metrics.items():
            with st.expander(f"📐 {metric_name}"):
                st.markdown(info["description"])
                st.code(info["formula"], language="sql")

        st.markdown("---")
        st.caption(f"Model: `{settings.LLM_MODEL}`")

    # Main area
    st.subheader("Ask a Question")

    # Example questions
    st.markdown("**Example questions:**")
    cols = st.columns(2)
    for i, question in enumerate(EXAMPLE_QUESTIONS):
        col = cols[i % 2]
        if col.button(f"💬 {question[:60]}...", key=f"ex_{i}", use_container_width=True):
            st.session_state["user_question"] = question

    question = st.text_area(
        "Your question",
        value=st.session_state.get("user_question", ""),
        height=80,
        placeholder="e.g. Show me the top 10 lines with the highest average delay in the last 30 days.",
        key="question_input",
    )

    generate_btn = st.button("🚀 Generate SQL", type="primary", use_container_width=True)

    if generate_btn and question.strip():
        with st.spinner("Generating SQL query..."):
            system_prompt = build_system_prompt()
            user_prompt = build_user_prompt(question.strip())
            result = generate_sql(system_prompt, user_prompt)

        status = result.get("status", "error")
        sql = result.get("sql", "")
        explanation = result.get("explanation", "")
        used_tables = result.get("used_tables", [])
        used_columns = result.get("used_columns", [])
        assumptions = result.get("assumptions", [])
        warnings_llm = result.get("warnings", [])

        if status == "error":
            st.error(f"❌ LLM Error: {explanation}")
            return

        if status == "clarification_needed":
            st.info(f"💬 Clarification needed: {explanation}")
            return

        if status == "unsupported":
            st.warning(f"⚠️ Cannot answer with available data: {explanation}")
            return

        # Validate SQL
        schema = get_schema_metadata()
        allowed_tables = set(schema.keys())
        validation = validate_sql(sql, allowed_tables)

        # Display results
        st.markdown("---")
        st.subheader("Generated SQL Query")

        if validation.is_valid:
            st.success("✅ SQL validation passed")
        else:
            st.error("❌ SQL validation failed — do not use this query")

        display_sql = validation.normalized_sql if validation.normalized_sql else sql
        st.code(display_sql, language="sql")

        # Open in Superset SQL Lab button
        superset_url = f"http://localhost:8088/sqllab/?sql={urllib.parse.quote(display_sql)}&dbid=1"
        st.link_button(
            "🔗 Open in Superset SQL Lab",
            superset_url,
            use_container_width=True,
            disabled=not validation.is_valid,
        )
        st.caption("Opens Superset SQL Lab with the query pre-filled. Review and run it manually.")

        if validation.errors:
            st.subheader("Validation Errors")
            for err in validation.errors:
                st.error(f"• {err}")

        if validation.warnings or warnings_llm:
            st.subheader("Warnings")
            for w in validation.warnings + warnings_llm:
                st.warning(f"• {w}")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Explanation")
            st.markdown(explanation)

            if assumptions:
                st.subheader("Assumptions")
                for a in assumptions:
                    st.markdown(f"- {a}")

        with col2:
            if used_tables:
                st.subheader("Used Tables")
                for t in used_tables:
                    st.markdown(f"- `{t}`")

            if used_columns:
                st.subheader("Used Columns")
                for c in used_columns:
                    st.markdown(f"- `{c}`")

    elif generate_btn:
        st.warning("Please enter a question first.")


if __name__ == "__main__":
    main()
