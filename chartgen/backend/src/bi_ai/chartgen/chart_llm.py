"""LLM calls for chart suggestion — thin wrapper around OpenRouter."""
from __future__ import annotations
import json
import os
import re

from openai import OpenAI, APIConnectionError, APIStatusError, AuthenticationError

SYSTEM_PROMPT = """You are an expert data visualization assistant embedded in Apache Superset.
Given a SQL query and its result columns, you suggest the best chart configuration.

## Available chart types and when to use them
- echarts_timeseries_line: time series with a date/timestamp column, shows trends over time
- echarts_timeseries_bar: categorical comparisons, rankings, distributions (non-time x-axis)
- pie: part-of-whole proportions (max 2-3 group_by columns, one metric)
- table: raw tabular data, many columns, no clear single metric
- big_number_total: single aggregated number (COUNT, SUM, AVG with no group_by)

## Rules
- If the query has a timestamp/date column AND a metric → echarts_timeseries_line
- If the query groups by a categorical column (line_id, direction, etc.) with a metric → echarts_timeseries_bar
- If the query has proportions or percentages → pie
- If the query returns one aggregated number → big_number_total
- Otherwise → table
- x_axis: use the first time/date column found, or the first group_by column for bar
- metrics: derive from SELECT aliases or aggregate expressions in the SQL
- group_by: other dimensions beyond x_axis (e.g. line_id when x_axis is event_timestamp)
- time_grain_sqla: "P1D" for daily, "P1W" for weekly, "P1M" for monthly (guess from query)

## Output format
Respond with a single JSON object only. No markdown, no code fences.
{
  "status": "success",
  "viz_type": "echarts_timeseries_line",
  "title": "Short descriptive title",
  "source_table": "goldlayer.delay_vw",
  "x_axis": "column_name_or_null",
  "metrics": [
    { "label": "Human label", "expressionType": "SQL", "sqlExpression": "AVG(mean_in_value)" }
  ],
  "group_by": ["line_id"],
  "adhoc_filters": ["tenant_id = 1", "event_timestamp >= CURRENT_DATE - INTERVAL '30 DAYS'"],
  "time_grain_sqla": "P1W",
  "explanation": "One sentence explaining why this chart type fits."
}

## Additional rules for source_table and adhoc_filters
- source_table: the schema-qualified table from the FROM clause (e.g. "goldlayer.delay_vw"). Use the main table; ignore CTEs or subqueries.
- adhoc_filters: each AND-separated condition from the WHERE clause as a separate string. Omit tenant_id filters if row-level security is expected to handle them, but include them if explicit in the SQL. Empty list if no WHERE clause.
"""


def _client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=os.environ["LLM_API_KEY"],
        default_headers={
            "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER", "https://github.com/tommasaso/bi-ai"),
            "X-Title": "BI-AI Chart Generator",
        },
    )


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(cleaned)


def suggest_chart(sql: str, columns: list[dict], question: str = "") -> dict:
    """Ask LLM to suggest a chart configuration for the given SQL + columns."""
    col_desc = ", ".join(f"{c['name']} ({c['type']})" for c in columns)
    user_msg = f"SQL:\n{sql}\n\nResult columns: {col_desc}"
    if question:
        user_msg += f"\n\nUser refinement request: {question}"

    client = _client()
    model = os.environ.get("LLM_MODEL", "qwen/qwen3-coder")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
        )
        raw = response.choices[0].message.content or ""
        result = _extract_json(raw)
        result.setdefault("status", "success")
        result.setdefault("metrics", [])
        result.setdefault("group_by", [])
        result.setdefault("x_axis", None)
        result.setdefault("source_table", None)
        result.setdefault("adhoc_filters", [])
        result.setdefault("time_grain_sqla", "P1D")
        result.setdefault("explanation", "")
        return result
    except AuthenticationError:
        return _err("Authentication failed. Check LLM_API_KEY.")
    except APIConnectionError:
        return _err("Cannot connect to LLM provider.")
    except APIStatusError as e:
        return _err(f"LLM API error {e.status_code}: {e.message}")
    except json.JSONDecodeError:
        raw_preview = locals().get("raw", "")[:200]
        return _err(f"LLM returned non-JSON: {raw_preview}")
    except Exception as e:
        return _err(f"Unexpected error: {e}")


def _err(message: str) -> dict:
    return {
        "status": "error",
        "explanation": message,
        "viz_type": "table",
        "title": "",
        "metrics": [],
        "group_by": [],
        "x_axis": None,
        "time_grain_sqla": "P1D",
    }
