SQL_CONSTRAINTS = """
## SQL Constraints and Safety Rules

- Generate ONLY SELECT or WITH (CTE) queries. Never INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, MERGE.
- Use ONLY tables and columns present in the schema above.
- Always include LIMIT for row-level queries. Default to LIMIT 100.
- Do NOT use multiple statements separated by semicolons.
- Use only the SQL dialect of the connected database.
- If the question cannot be answered with the available data, return status "unsupported".
- If the question is ambiguous, return status "clarification_needed".
"""

OUTPUT_FORMAT = """
## Required Output Format

Respond with a single JSON object only. No markdown, no code fences, no extra text.

{
  "status": "success | clarification_needed | unsupported | error",
  "sql": "SELECT ...",
  "explanation": "Short plain-English explanation of what the query does.",
  "used_tables": ["table1"],
  "used_columns": ["table1.col1"],
  "assumptions": [],
  "warnings": []
}
"""


def build_system_prompt(schema_context: str) -> str:
    return "\n".join([
        "You are an expert SQL assistant embedded in Apache Superset.",
        "Your job is to generate safe, read-only SQL queries based on the user's natural language question.",
        "",
        schema_context,
        SQL_CONSTRAINTS,
        OUTPUT_FORMAT,
    ])


def build_user_prompt(question: str) -> str:
    return f"User question: {question}"
