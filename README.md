# bi-ai — AI Extensions for Apache Superset

Two native Superset extensions that bring AI-assisted SQL generation and chart creation directly into the SQL Lab interface, built for a multi-tenant public transport analytics platform.

---

## Contents

- [Architecture overview](#architecture-overview)
- [Extensions](#extensions)
  - [text2sql — Ask AI](#text2sql--ask-ai)
  - [chartgen — AI Chart](#chartgen--ai-chart)
- [Data model](#data-model)
- [Local development](#local-development)
- [Deployment](#deployment)
- [Environment variables](#environment-variables)
- [Production gaps](#production-gaps)

---

## Architecture overview

```
┌──────────────────────────────────────────────────────────┐
│                    Apache Superset                        │
│                                                          │
│  SQL Lab                                                 │
│  ┌──────────────────────┐  ┌─────────────────────────┐  │
│  │   SQL Editor         │  │  Right Sidebar          │  │
│  │   (Monaco)           │  │                         │  │
│  │                      │  │  ┌─────────────────┐    │  │
│  │  SELECT ...          │  │  │  Ask AI         │    │  │
│  │  FROM goldlayer.X    │  │  │  (text2sql)     │    │  │
│  │                      │  │  ├─────────────────┤    │  │
│  │  ──── Run ────       │  │  │  AI Chart       │    │  │
│  │  Results table       │  │  │  (chartgen)     │    │  │
│  └──────────────────────┘  └─────────────────────────┘  │
│                                                          │
│  Extension APIs (Flask / FAB)                            │
│  POST /extensions/bi-ai/text2sql/generate                │
│  POST /extensions/bi-ai/chartgen/suggest                 │
│  POST /extensions/bi-ai/chartgen/create                  │
└──────────────────┬───────────────────────────────────────┘
                   │ LLM_API_KEY
                   ▼
            OpenRouter API
            (qwen/qwen3-coder or any model)
                   │
                   ▼
         LLM generates SQL / chart config
```

```
PostgreSQL (goldlayer schema)
├── delay_vw          — stop-level delay metrics
├── ridership_vw      — boarding/alighting counts
├── punctuality_index_vw
├── congestion_rate_vw
├── number_of_trips_vw
└── number_of_stops_vw

All views include tenant_id for row-level isolation.
```

---

## Extensions

### text2sql — Ask AI

Converts natural language questions into SQL queries using the goldlayer schema as context.

**Flow:**

```
User types question
      │
      ▼
POST /extensions/bi-ai/text2sql/generate
      │
      ├─ get_schema_info(database_id)   ← introspects goldlayer views via Superset ORM
      ├─ build_system_prompt(schema, tenant_id)
      ├─ generate_sql(system_prompt, user_prompt)  ← LLM call (OpenRouter)
      └─ validate_sql(sql, allowed_tables, tenant_id)  ← sqlglot parse + normalization
            │
            ▼
      SQL placed in editor + warnings shown
```

**Backend modules:**

| File | Responsibility |
|------|---------------|
| `api.py` | Flask endpoint `/generate` |
| `llm.py` | OpenRouter client, JSON extraction from LLM response |
| `metadata.py` | Schema introspection via Superset `Database` ORM |
| `prompt_builder.py` | System prompt with schema context, SQL constraints, domain knowledge |
| `sql_validator.py` | sqlglot parse, keyword blocklist, LIMIT enforcement, tenant_id injection |
| `tenant.py` | Extracts tenant_id from current user's JWT claims or RLS rules |

**LLM output format:**

```json
{
  "status": "success",
  "sql": "SELECT ...",
  "explanation": "...",
  "used_tables": ["delay_vw"],
  "used_columns": ["line_name", "mean_in_value"],
  "warnings": []
}
```

---

### chartgen — AI Chart

Suggests a chart type from SQL in the editor, then creates the chart in Superset linked to an existing shared dataset when possible.

**Flow:**

```
User clicks "Generate Chart Suggestion"
      │
      ▼
POST /extensions/bi-ai/chartgen/suggest
      │
      └─ suggest_chart(sql, columns, question)  ← LLM analyzes SQL
            │
            ▼
      Chart type + config shown in sidebar

User clicks "Create Chart"
      │
      ▼
POST /extensions/bi-ai/chartgen/create
      │
      ├─ _find_existing_dataset(source_table)
      │       ├─ Found → reuse physical dataset  (dashboard filters work)
      │       └─ Not found → create virtual dataset from SQL (fallback)
      │
      ├─ _build_form_data(viz_type, suggestion, dataset)
      │       ├─ physical dataset: use LLM metrics/axes, remap SQL aliases to real columns
      │       └─ virtual dataset: introspect output columns, auto-build SUM() metrics
      │
      └─ Slice (chart) created → redirect to Explore
```

**Dataset reuse strategy:**

When `source_table` is identified (e.g. `goldlayer.ridership_vw`), chartgen looks up a Superset dataset with `schema=goldlayer`, `table_name=ridership_vw`, `sql=NULL`. If found, the chart is bound to that shared datasource — meaning dashboard native filters applied to that dataset will filter all AI-generated charts on that view together.

**LLM output format:**

```json
{
  "status": "success",
  "viz_type": "echarts_timeseries_line",
  "title": "Ridership Trends by Line",
  "source_table": "goldlayer.ridership_vw",
  "x_axis": "event_timestamp",
  "metrics": [
    { "label": "Total Passengers", "expressionType": "SQL", "sqlExpression": "SUM(tot_ridership)" }
  ],
  "group_by": ["line_name"],
  "adhoc_filters": ["tenant_id = 1", "event_timestamp >= CURRENT_DATE - INTERVAL '60 DAYS'"],
  "time_grain_sqla": "P1W",
  "explanation": "Line chart shows ridership trend over time grouped by line."
}
```

**Supported viz types:**

| viz_type | Use case |
|----------|----------|
| `echarts_timeseries_line` | Trends over time with a date/timestamp x-axis |
| `echarts_timeseries_bar` | Categorical comparisons, rankings |
| `pie` | Part-of-whole proportions |
| `big_number_total` | Single aggregated KPI |
| `table` | Multi-column raw output |

---

## Data model

```
goldlayer schema (PostgreSQL)
│
├── *_vw views — public API for queries
│   ├── tenant_id      BIGINT    — tenant isolation key
│   ├── line_id        VARCHAR   — transit line identifier
│   ├── line_name      VARCHAR   — human readable line name
│   ├── event_timestamp TIMESTAMP — CET timezone
│   ├── peaks          INTEGER   — 0=AM peak, 1=off-peak, 2=PM peak, 3=evening, 4=night
│   └── ... domain-specific columns
│
└── Delay domain: mean_in_value (seconds), congestion_rate (0.0–1.0)
    Ridership domain: tot_boarding, tot_alighting, tot_ridership
```

Superset datasets registered on these views (with `sql=NULL`) serve as the shared datasources for dashboard filtering.

---

## Local development

### Prerequisites

- Docker + Docker Compose
- Node.js 18+
- Python 3.11+
- An OpenRouter API key (or compatible LLM endpoint)

### Start Superset

```bash
cd /path/to/apache-superset
docker compose up -d
```

### Build and deploy an extension

```bash
# Build frontend
cd chartgen/frontend
npm install
npm run build

# Package extension
cd ..
zip chartgen-0.1.0.supx \
  backend/src/bi_ai/chartgen/*.py \
  frontend/dist/*.js

# Copy to Superset extensions directory
cp chartgen-0.1.0.supx /path/to/superset/extensions/

# Restart to pick up changes
docker compose restart superset
```

Same process for `text2sql/`.

### Verify extension loaded

```bash
docker logs <superset-container> 2>&1 | grep "Loaded extension"
# Expected:
# INFO: Loaded extension 'bi-ai.chartgen' from .../chartgen-0.1.0.supx
# INFO: Loaded extension 'bi-ai.text2sql' from .../text2sql-0.1.0.supx
```

---

## Deployment

Extensions are packaged as `.supx` files (zip archives) and discovered automatically by Superset at startup from a configured extensions directory.

### Superset configuration

In `superset_config.py`:

```python
EXTENSIONS_CONF = {
    "discovery_path": "/app/extensions",
}
```

### Required environment variables in the Superset container

See [Environment variables](#environment-variables) below.

### Deploy new version

```bash
# 1. Build and package
cd chartgen && zip -u chartgen-0.1.0.supx backend/src/bi_ai/chartgen/*.py

# 2. Restart Superset (zero-downtime restart preferred in production)
docker compose restart superset
```

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_API_KEY` | Yes | — | OpenRouter (or compatible) API key |
| `LLM_BASE_URL` | No | `https://openrouter.ai/api/v1` | LLM API base URL |
| `LLM_MODEL` | No | `qwen/qwen3-coder` | Model identifier |
| `OPENROUTER_HTTP_REFERER` | No | `https://github.com/tommasaso/bi-ai` | Sent as HTTP-Referer to OpenRouter |

Set these in the Superset Docker environment (`docker-compose.yml` or Kubernetes secrets).

---

## Production gaps

The extensions work end-to-end in a development environment. The following gaps should be addressed before production deployment.

### 1. Tenant isolation

| Gap | Risk | Fix |
|-----|------|-----|
| `tenant.py` reads `tenant_id` from JWT claim; claim name must match the Keycloak token exactly | Cross-tenant data leak if claim not found | Verify claim name in Keycloak token, add hard failure (not `None` default) when tenant not found |
| `chartgen` trusts the LLM-generated `adhoc_filters` for tenant scoping | LLM could omit the tenant filter if SQL doesn't include it | Enforce server-side tenant filter injection in `/create` endpoint, same as text2sql does |
| Virtual dataset fallback in chartgen always uses `schema="goldlayer"` | Breaks in multi-schema setups | Make schema configurable via env var or detect from `source_table` |

### 2. LLM reliability and cost

| Gap | Risk | Fix |
|-----|------|-----|
| LLM calls are synchronous with no timeout config | Superset request timeout kills in-flight LLM calls | Set `timeout` on OpenAI client; add async or background task for slow models |
| No retry on transient failures (429, 503) | Single failure shown as error | Add exponential backoff retry (tenacity or manual) |
| No rate limiting | Unbounded API cost from heavy usage | Add per-user or per-tenant rate limit in the Flask endpoint |
| No response caching | Same SQL triggers multiple identical LLM calls | Cache `suggest_chart(sql)` by SHA256(sql) with short TTL (e.g. Redis) |
| Prompt injection via user question | LLM could be manipulated to generate harmful SQL | Add input sanitization layer; validate output SQL with sqlglot regardless of source |

### 3. Chart and dataset management

| Gap | Risk | Fix |
|-----|------|-----|
| Virtual dataset fallback creates entries in `tables` that accumulate over time | Dataset list grows unbounded | Add a scheduled cleanup job or TTL-based expiry for `is_sqllab_view=True` datasets |
| AI-generated charts are only accessible to the creator | Other dashboard editors can't add the chart | After creation, explicitly assign default permissions matching the organization's Superset roles |
| `_find_existing_dataset` matches only physical tables (`sql=NULL`); datasets registered as virtual views are missed | Dataset not found → fallback to new virtual dataset even when a virtual dataset already covers that view | Extend lookup to match also `sql IS NOT NULL` datasets for the same logical view |
| x_axis remapping is heuristic (first temporal column) | Wrong axis for charts with multiple timestamp columns | Pass physical column types to LLM in the `/suggest` request so it can choose the right column name directly |

### 4. Security

| Gap | Risk | Fix |
|-----|------|-----|
| `create_chart` calls `db.session.commit()` without rollback on partial failure | Partial state (dataset without chart, or vice versa) left in DB | Wrap in `try/except` with explicit `db.session.rollback()` |
| Extension API endpoints rely only on Superset's `@protect()` | Superset session-based auth; does not enforce fine-grained object-level permissions | Add explicit permission checks per tenant |
| No audit log of AI-generated SQL or chart creation | Compliance and debugging gap | Emit structured log events (user, tenant, sql, chart_id, timestamp) for each AI action |

### 5. CI/CD and packaging

| Gap | Risk | Fix |
|-----|------|-----|
| `.supx` files are committed to git as binary blobs | Merge conflicts, bloated history | Build `.supx` in CI on tag push; store in artifact registry (S3, GitHub Releases) |
| No automated tests for extension backend | Regressions undetected | Add pytest suite with a Superset app fixture; mock LLM calls |
| No version bumping workflow | `0.1.0` forever | Follow semver; bump version in `manifest.json` on every release |
| `frontend/dist/` is committed to git | Large binary churn | Move to CI build artifacts; exclude from git |

### 6. Observability

| Gap | Risk | Fix |
|-----|------|-----|
| LLM call latency and error rate not tracked | Can't detect model degradation | Add OpenTelemetry spans around LLM calls; export to existing monitoring stack |
| No structured error response format | Frontend shows raw Python tracebacks in error field | Standardize error responses: `{status, code, message}` |
| `fetch_metadata()` failure is silently swallowed | Charts created with empty column metadata | Log warning with dataset_id and SQL when `fetch_metadata` raises |

### 7. Keycloak / SSO integration

| Gap | Risk | Fix |
|-----|------|-----|
| `tenant.py` tries multiple claim paths (`tenant_id`, fallback to RLS) but has no explicit Keycloak mapper config | Silent fallback returns `None` tenant | Define and enforce a specific Keycloak mapper that sets `tenant_id` in the token; remove the fallback |
| Extensions don't validate token expiry independently | Expired Superset session could reuse a cached tenant value | Rely on Superset's session refresh; ensure session timeout is aligned with Keycloak token TTL |

---

## Repository structure

```
bi-ai/
├── text2sql/                   # "Ask AI" extension — natural language → SQL
│   ├── extension.json
│   ├── text2sql-0.1.0.supx    # Built package (deploy this)
│   ├── backend/src/bi_ai/text2sql/
│   │   ├── api.py             # POST /extensions/bi-ai/text2sql/generate
│   │   ├── llm.py             # OpenRouter wrapper
│   │   ├── metadata.py        # Goldlayer schema introspection
│   │   ├── prompt_builder.py  # System prompt + domain knowledge
│   │   ├── sql_validator.py   # sqlglot parse, tenant injection
│   │   └── tenant.py          # Tenant resolution from JWT
│   └── frontend/src/
│       └── panel/Text2SqlPanel.tsx
│
├── chartgen/                   # "AI Chart" extension — SQL → Superset chart
│   ├── manifest.json
│   ├── chartgen-0.1.0.supx   # Built package (deploy this)
│   ├── backend/src/bi_ai/chartgen/
│   │   ├── api.py             # POST /suggest, POST /create
│   │   ├── chart_llm.py       # LLM chart suggestion
│   │   └── chart_builder.py   # Superset ORM chart + dataset creation
│   └── frontend/src/
│       └── panel/ChartGenPanel.tsx
│
├── superset-text2sql-poc/      # Standalone Streamlit POC (not for production)
└── dev/                        # Setup scripts (goldlayer SQL, seed data)
```
