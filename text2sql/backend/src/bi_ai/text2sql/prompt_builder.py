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

### Common columns in all KPI views
- `tenant_id` (bigint) — do NOT add to your SQL; the system injects it automatically
- `line_id` (varchar) — e.g. 'M1', 'M2', '4', '9'
- `line_name` (varchar) — e.g. 'Metro M1', 'Bus 9'
- `direction` (varchar) — 'outbound' or 'inbound'
- `destination` (varchar) — terminus stop name
- `event_timestamp` (timestamptz) — start of the weekly aggregation period (UTC)
- `peaks` (int) — 0=AM peak, 1=off-peak, 2=PM peak, 3=evening, 4=night

### delay_vw — delay statistics per stop/week
- `stop_id`, `stop_name` — individual stop
- `mean_out_value`, `mean_in_value` — average delay in SECONDS (integer)
- `min_*/max_*/dev_std_*_value` — min/max/stddev delay in SECONDS

### punctuality_index_vw — punctuality per stop/week
- `stop_id`, `stop_name` — individual stop
- `punctuality_soft`, `punctuality_medium`, `punctuality_hard` — ratio (0.0–1.0) of trips on time
  (soft=15s threshold, medium=10s, hard=5s; e.g. 0.77 means 77% of trips on time)
- `hard_in/out`, `medium_in/out`, `soft_in/out`, `outside_th_in/out` — trip counts per threshold bucket

### congestion_rate_vw — vehicle load per stop/week
- `stop_id`, `stop_name`
- `mean_congestion_rate` — average load ratio (0.0–1.0); 1.0 = full capacity
- `min/max/dev_std_congestion_rate`

### ridership_vw — passenger counts per stop/week
- `stop_id`, `stop_name`
- `tot_boarding`, `tot_alighting`, `tot_ridership`, `avg_ridership`, `max_ridership` (integer)

### number_of_trips_vw — trip completion per line/week (no stop_id column)
- `expected_trips`, `completed_trips`, `late_completed_trips`, `early_completed_trips` (integer)
- `completion_rate` (double) — ratio of completed to expected trips

### PostgreSQL time filtering examples
- Last 30 days:    `event_timestamp >= NOW() - INTERVAL '30 days'`
- Current month:   `DATE_TRUNC('month', event_timestamp) = DATE_TRUNC('month', NOW())`
- Specific month:  `event_timestamp >= '2026-04-01' AND event_timestamp < '2026-05-01'`
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
