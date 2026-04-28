from app.metadata import get_schema_metadata, build_metadata_context
from app.metrics_catalog import load_metrics_catalog, build_metrics_context

EXAMPLE_QUERIES = """
## Example Queries

### Top 10 lines by average delay (last 30 days)
```sql
SELECT
    l.line_id,
    l.line_name,
    AVG(se.arrival_delay_seconds) AS average_delay_seconds
FROM stop_events se
JOIN lines l ON se.line_id = l.line_id
WHERE se.service_date >= DATE('now', '-30 days')
GROUP BY l.line_id, l.line_name
ORDER BY average_delay_seconds DESC
LIMIT 10;
```

### Punctuality rate by line for current month
```sql
SELECT
    l.line_name,
    SUM(CASE WHEN se.arrival_delay_seconds <= 300 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS punctuality_rate
FROM stop_events se
JOIN lines l ON se.line_id = l.line_id
WHERE strftime('%Y-%m', se.service_date) = strftime('%Y-%m', 'now')
GROUP BY l.line_id, l.line_name
ORDER BY punctuality_rate DESC;
```

### Daily passenger count trend (last 60 days)
```sql
SELECT
    DATE(pc.event_timestamp) AS day,
    SUM(pc.boarding_count) AS total_boardings
FROM passenger_counts pc
WHERE DATE(pc.event_timestamp) >= DATE('now', '-60 days')
GROUP BY DATE(pc.event_timestamp)
ORDER BY day ASC
LIMIT 60;
```
"""

SQL_CONSTRAINTS = """
## SQL Constraints and Safety Rules

- Generate ONLY SELECT or WITH (CTE) queries. Never INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, MERGE.
- Use ONLY tables and columns that exist in the schema above. Do NOT invent tables or columns.
- Always include LIMIT when returning raw row-level data. Default to LIMIT 100 if unsure.
- Do NOT include multiple statements separated by semicolons.
- Use only SQLite-compatible SQL syntax and functions.
- For date filtering use SQLite functions like DATE('now', '-30 days'), strftime(), DATE().
- Use meaningful aliases for computed columns.
- Use JOIN only when necessary.
- If the question cannot be answered with the available data, return status "unsupported".
- If the question is ambiguous, return status "clarification_needed" and explain what is unclear.
"""

OUTPUT_FORMAT = """
## Required Output Format

Respond with a single JSON object only. No markdown. No code blocks. No extra text.

{
  "status": "success | clarification_needed | unsupported",
  "sql": "SELECT ...",
  "explanation": "Short explanation of what the query does.",
  "used_tables": ["table1", "table2"],
  "used_columns": ["table1.col1", "table2.col2"],
  "assumptions": ["assumption1", "assumption2"],
  "warnings": ["warning1"]
}

If status is "clarification_needed" or "unsupported", set "sql" to an empty string "".
"""


def build_system_prompt() -> str:
    schema = get_schema_metadata()
    metadata_ctx = build_metadata_context(schema)
    metrics = load_metrics_catalog()
    metrics_ctx = build_metrics_context(metrics)

    parts = [
        "You are an expert SQL assistant for a public transport analytics platform.",
        "Your job is to generate safe, read-only SQL queries for SQLite based on the user's natural language question.",
        "",
        metadata_ctx,
        metrics_ctx,
        EXAMPLE_QUERIES,
        SQL_CONSTRAINTS,
        OUTPUT_FORMAT,
    ]
    return "\n".join(parts)


def build_user_prompt(question: str) -> str:
    return f"User question: {question}"
