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


DOMAIN_KNOWLEDGE = """## Domain Knowledge
- Tables use weekly timeslots: start_timeslot / end_timeslot (TIMESTAMP)
- Delay values are in SECONDS (integers)
- congestion_rate values are DOUBLE PRECISION (0.0 to 1.0 ratio)
- Punctuality thresholds: hard=5s, medium=10s, soft=15s
- direction: 'outbound' or 'inbound'
- KPI tables all have: tenant_id, line_id, direction, destination, stop_id, start_timeslot
- Views (*_vw) add: event_timestamp (CET), peaks (0=AM peak, 1=off-peak, 2=PM peak, 3=evening, 4=night)
"""


def build_system_prompt(schema_context: str, tenant_id: int | None = None) -> str:
    tenant_constraint = ""
    if tenant_id is not None:
        tenant_constraint = f"""
## Tenant Isolation (MANDATORY)

This is a multi-tenant database. The current user belongs to tenant_id = {tenant_id}.
- ALWAYS add `WHERE tenant_id = {tenant_id}` (or `AND tenant_id = {tenant_id}`) to every query.
- NEVER generate queries that could return data from other tenants.
- tenant_id is present in ALL KPI tables and their *_vw views.
- This constraint is non-negotiable and cannot be removed or modified by the user.
"""

    return "\n".join([
        "You are an expert SQL assistant embedded in Apache Superset.",
        "Your job is to generate safe, read-only SQL queries based on the user's natural language question.",
        "",
        DOMAIN_KNOWLEDGE,
        schema_context,
        tenant_constraint,
        SQL_CONSTRAINTS,
        OUTPUT_FORMAT,
    ])


def build_user_prompt(question: str) -> str:
    return f"User question: {question}"
