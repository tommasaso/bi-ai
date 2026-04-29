# Implementation Plan: Production Alignment + 3-Layer Tenant Isolation

**Status:** Ready to implement  
**Constraint:** Modifiche SOLO in `bi-ai/` — nessun tocco a apache-superset, kpi-proxy, bi-tool, bi-user-management-adapter  
**Obiettivo:** Allineare demo data allo schema goldlayer di produzione + implementare tenant isolation a 3 layer

---

## Architettura target

```
Superset User (admin/atm_user/gtt_user)
  → Layer 3: Extension prompt injection (tenant_id nel prompt + post-processing sqlglot)
  → Layer 2: Superset RLS (WHERE tenant_id = X automatico sulle views)
  → Layer 1: PostgreSQL RLS policies (FORCE ROW LEVEL SECURITY sulle tabelle raw)
  → goldlayer schema (PostgreSQL, stesso DB di Superset: superset:superset@localhost:5432/superset)
```

---

## File da creare/modificare (tutti in bi-ai/)

```
bi-ai/
├── dev/
│   ├── IMPLEMENTATION_PLAN.md       ← questo file
│   ├── setup_goldlayer.sql          ← crea schema + tabelle + views + RLS policies PG
│   ├── seed_goldlayer.py            ← genera dati demo multi-tenant (2 operatori)
│   ├── setup_superset.py            ← seed Superset via API (DB conn, datasets, roles, RLS)
│   └── docker-compose.override.yml  ← estende apache-superset con goldlayer init
├── superset-text2sql-poc/app/
│   └── seed_demo_data.py            ← REWRITE con schema goldlayer
└── text2sql/backend/src/bi_ai/text2sql/
    ├── tenant.py                    ← NUOVO: risolve tenant_id dal contesto Flask
    ├── api.py                       ← UPDATE: inietta tenant_id
    ├── prompt_builder.py            ← UPDATE: vincoli tenant nel system prompt
    └── sql_validator.py             ← UPDATE: post-processing sqlglot aggiunge WHERE tenant_id
```

---

## Step 1: dev/setup_goldlayer.sql

Schema goldlayer **identico** ai Liquibase di kpi-proxy (0.0.1.1 + 0.0.1.2 + 0.0.1.3).  
Si esegue sul PostgreSQL di apache-superset (`superset:superset@localhost:5432/superset`).

### Cosa contiene:
```sql
-- 1. Schema
CREATE SCHEMA IF NOT EXISTS goldlayer;

-- 2. Tabella operator (tenant registry)
CREATE TABLE IF NOT EXISTS goldlayer.operator (
    id                 BIGINT PRIMARY KEY,
    tenant_id          BIGINT NOT NULL UNIQUE,
    name               VARCHAR NOT NULL,
    lang               VARCHAR,
    timezone           VARCHAR,
    creation_timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);
INSERT INTO goldlayer.operator (id, tenant_id, name, lang, timezone, creation_timestamp)
VALUES
    (1, 1, 'ATM Milano',  'it', 'Europe/Rome', NOW()),
    (2, 2, 'GTT Torino',  'it', 'Europe/Rome', NOW())
ON CONFLICT DO NOTHING;

-- 3. Tabella thresholds
CREATE TABLE IF NOT EXISTS goldlayer.thresholds (
    id                   BIGINT PRIMARY KEY,
    tenant_id            BIGINT,
    soft_threshold_in    BIGINT,
    soft_threshold_out   BIGINT,
    medium_threshold_in  BIGINT,
    medium_threshold_out BIGINT,
    hard_threshold_in    BIGINT,
    hard_threshold_out   BIGINT,
    creation_timestamp   TIMESTAMP
);
INSERT INTO goldlayer.thresholds VALUES (1,1,15,15,10,10,5,5,NOW()) ON CONFLICT DO NOTHING;
INSERT INTO goldlayer.thresholds VALUES (2,2,15,15,10,10,5,5,NOW()) ON CONFLICT DO NOTHING;

-- 4. KPI tables (schema esatto da 0.0.1.1)
CREATE TABLE IF NOT EXISTS goldlayer.delay (
    start_timeslot     TIMESTAMP NOT NULL,
    end_timeslot       TIMESTAMP NOT NULL,
    tenant_id          BIGINT    NOT NULL,
    line_id            VARCHAR   NOT NULL,
    line_name          VARCHAR,
    destination        VARCHAR   NOT NULL,
    direction          VARCHAR   NOT NULL,
    stop_id            VARCHAR   NOT NULL,
    stop_name          VARCHAR   NOT NULL,
    latitude           DOUBLE PRECISION,
    longitude          DOUBLE PRECISION,
    min_in_value       INTEGER,
    mean_in_value      INTEGER,
    dev_std_in_value   INTEGER,
    max_in_value       INTEGER,
    min_out_value      INTEGER,
    mean_out_value     INTEGER,
    dev_std_out_value  INTEGER,
    max_out_value      INTEGER,
    creation_timestamp TIMESTAMP NOT NULL,
    CONSTRAINT delay_pk PRIMARY KEY (start_timeslot, end_timeslot, tenant_id, line_id, destination, direction, stop_id)
);

CREATE TABLE IF NOT EXISTS goldlayer.congestion_rate (
    start_timeslot     TIMESTAMP NOT NULL,
    end_timeslot       TIMESTAMP NOT NULL,
    tenant_id          BIGINT    NOT NULL,
    line_id            VARCHAR   NOT NULL,
    line_name          VARCHAR,
    destination        VARCHAR   NOT NULL,
    direction          VARCHAR   NOT NULL,
    stop_id            VARCHAR   NOT NULL,
    stop_name          VARCHAR   NOT NULL,
    latitude           DOUBLE PRECISION,
    longitude          DOUBLE PRECISION,
    min_value          DOUBLE PRECISION,
    mean_value         DOUBLE PRECISION,
    dev_std_value      DOUBLE PRECISION,
    max_value          DOUBLE PRECISION,
    creation_timestamp TIMESTAMP NOT NULL,
    CONSTRAINT congestion_rate_pk PRIMARY KEY (start_timeslot, end_timeslot, tenant_id, line_id, destination, direction, stop_id)
);

CREATE TABLE IF NOT EXISTS goldlayer.punctuality_index (
    start_timeslot     TIMESTAMP NOT NULL,
    end_timeslot       TIMESTAMP NOT NULL,
    tenant_id          BIGINT    NOT NULL,
    line_id            VARCHAR   NOT NULL,
    line_name          VARCHAR,
    destination        VARCHAR   NOT NULL,
    direction          VARCHAR   NOT NULL,
    stop_id            VARCHAR   NOT NULL,
    stop_name          VARCHAR   NOT NULL,
    latitude           DOUBLE PRECISION,
    longitude          DOUBLE PRECISION,
    hard_in            BIGINT,
    medium_in          BIGINT,
    soft_in            BIGINT,
    outside_th_in      BIGINT,
    hard_out           BIGINT,
    medium_out         BIGINT,
    soft_out           BIGINT,
    outside_th_out     BIGINT,
    creation_timestamp TIMESTAMP NOT NULL,
    CONSTRAINT punctuality_index_pk PRIMARY KEY (start_timeslot, end_timeslot, tenant_id, line_id, direction, destination, stop_id)
);

CREATE TABLE IF NOT EXISTS goldlayer.ridership (
    start_timeslot     TIMESTAMP NOT NULL,
    end_timeslot       TIMESTAMP NOT NULL,
    tenant_id          BIGINT    NOT NULL,
    line_id            VARCHAR   NOT NULL,
    line_name          VARCHAR,
    destination        VARCHAR   NOT NULL,
    direction          VARCHAR   NOT NULL,
    stop_id            VARCHAR   NOT NULL,
    stop_name          VARCHAR   NOT NULL,
    latitude           DOUBLE PRECISION,
    longitude          DOUBLE PRECISION,
    tot_boarding       INTEGER,
    tot_alighting      INTEGER,
    tot_ridership      INTEGER,
    avg_ridership      INTEGER,
    max_ridership      INTEGER,
    creation_timestamp TIMESTAMP NOT NULL,
    CONSTRAINT ridership_pk PRIMARY KEY (start_timeslot, end_timeslot, tenant_id, line_id, destination, direction, stop_id)
);

CREATE TABLE IF NOT EXISTS goldlayer.number_of_trips (
    start_timeslot        TIMESTAMP NOT NULL,
    end_timeslot          TIMESTAMP NOT NULL,
    tenant_id             BIGINT    NOT NULL,
    line_id               VARCHAR   NOT NULL,
    line_name             VARCHAR,
    direction             VARCHAR   NOT NULL,
    destination           VARCHAR   NOT NULL,
    expected_trips        INTEGER,
    completed_trips       INTEGER,
    late_completed_trips  INTEGER,
    early_completed_trips INTEGER,
    creation_timestamp    TIMESTAMP,
    CONSTRAINT number_of_trips_pk PRIMARY KEY (start_timeslot, end_timeslot, tenant_id, line_id, direction, destination)
);

CREATE TABLE IF NOT EXISTS goldlayer.number_of_stops (
    start_timeslot        TIMESTAMP NOT NULL,
    end_timeslot          TIMESTAMP NOT NULL,
    tenant_id             BIGINT    NOT NULL,
    line_id               VARCHAR   NOT NULL,
    line_name             VARCHAR,
    destination           VARCHAR   NOT NULL,
    direction             VARCHAR   NOT NULL,
    stop_id               VARCHAR   NOT NULL,
    stop_name             VARCHAR,
    latitude              DOUBLE PRECISION,
    longitude             DOUBLE PRECISION,
    scheduled_stops       INTEGER,
    completed_stops       INTEGER,
    late_completed_stops  INTEGER,
    early_completed_stops INTEGER,
    creation_timestamp    TIMESTAMP NOT NULL,
    CONSTRAINT number_of_stops_pk PRIMARY KEY (start_timeslot, end_timeslot, tenant_id, line_id, destination, direction, stop_id)
);

-- 5. Views (da 0.0.1.3) — generalizzate (senza filtro hardcoded su line_id specifiche)
CREATE OR REPLACE VIEW goldlayer.delay_vw AS
SELECT
    tenant_id,
    line_id,
    line_name,
    destination,
    direction,
    stop_id,
    stop_name,
    start_timeslot::timestamp WITH TIME ZONE AT TIME ZONE 'CET' AS event_timestamp,
    CASE
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 7  AND EXTRACT(hour FROM start_timeslot)::int < 9  THEN 0
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 9  AND EXTRACT(hour FROM start_timeslot)::int < 16 THEN 1
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 16 AND EXTRACT(hour FROM start_timeslot)::int < 19 THEN 2
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 19 AND EXTRACT(hour FROM start_timeslot)::int < 24 THEN 3
        ELSE 4
    END AS peaks,
    min_in_value, mean_in_value, dev_std_in_value, max_in_value,
    min_out_value, mean_out_value, dev_std_out_value, max_out_value,
    latitude, longitude
FROM goldlayer.delay
WHERE mean_in_value IS NOT NULL;

CREATE OR REPLACE VIEW goldlayer.congestion_rate_vw AS
SELECT
    tenant_id,
    line_id,
    line_name,
    destination,
    direction,
    stop_id,
    stop_name,
    start_timeslot::timestamp WITH TIME ZONE AT TIME ZONE 'CET' AS event_timestamp,
    CASE
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 7  AND EXTRACT(hour FROM start_timeslot)::int < 9  THEN 0
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 9  AND EXTRACT(hour FROM start_timeslot)::int < 16 THEN 1
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 16 AND EXTRACT(hour FROM start_timeslot)::int < 19 THEN 2
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 19 AND EXTRACT(hour FROM start_timeslot)::int < 24 THEN 3
        ELSE 4
    END AS peaks,
    GREATEST(0, min_value) AS min_congestion_rate,
    GREATEST(0, max_value) AS max_congestion_rate,
    GREATEST(0, mean_value) AS mean_congestion_rate,
    GREATEST(0, dev_std_value) AS dev_std_congestion_rate,
    latitude, longitude
FROM goldlayer.congestion_rate
WHERE min_value IS NOT NULL;

CREATE OR REPLACE VIEW goldlayer.punctuality_index_vw AS
WITH base AS (
    SELECT *,
           start_timeslot::timestamp WITH TIME ZONE AT TIME ZONE 'CET' AS event_timestamp
    FROM goldlayer.punctuality_index
)
SELECT
    tenant_id,
    line_id,
    line_name,
    destination,
    direction,
    stop_id,
    stop_name,
    event_timestamp,
    CASE
        WHEN EXTRACT(hour FROM event_timestamp)::int >= 7  AND EXTRACT(hour FROM event_timestamp)::int < 9  THEN 0
        WHEN EXTRACT(hour FROM event_timestamp)::int >= 9  AND EXTRACT(hour FROM event_timestamp)::int < 16 THEN 1
        WHEN EXTRACT(hour FROM event_timestamp)::int >= 16 AND EXTRACT(hour FROM event_timestamp)::int < 19 THEN 2
        WHEN EXTRACT(hour FROM event_timestamp)::int >= 19 AND EXTRACT(hour FROM event_timestamp)::int < 24 THEN 3
        ELSE 4
    END AS peaks,
    hard_in, medium_in, soft_in, outside_th_in,
    hard_out, medium_out, soft_out, outside_th_out,
    CASE WHEN (soft_in + outside_th_in) > 0
         THEN soft_in::double precision / (soft_in + outside_th_in)
         ELSE 0 END AS punctuality_soft,
    CASE WHEN (soft_in + outside_th_in) > 0
         THEN medium_in::double precision / (soft_in + outside_th_in)
         ELSE 0 END AS punctuality_medium,
    CASE WHEN (soft_in + outside_th_in) > 0
         THEN hard_in::double precision / (soft_in + outside_th_in)
         ELSE 0 END AS punctuality_hard,
    latitude, longitude
FROM base
WHERE soft_in IS NOT NULL;

CREATE OR REPLACE VIEW goldlayer.ridership_vw AS
SELECT
    tenant_id,
    line_id,
    line_name,
    destination,
    direction,
    stop_id,
    stop_name,
    start_timeslot::timestamp WITH TIME ZONE AT TIME ZONE 'CET' AS event_timestamp,
    CASE
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 7  AND EXTRACT(hour FROM start_timeslot)::int < 9  THEN 0
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 9  AND EXTRACT(hour FROM start_timeslot)::int < 16 THEN 1
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 16 AND EXTRACT(hour FROM start_timeslot)::int < 19 THEN 2
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 19 AND EXTRACT(hour FROM start_timeslot)::int < 24 THEN 3
        ELSE 4
    END AS peaks,
    tot_boarding, tot_alighting, tot_ridership, avg_ridership, max_ridership,
    latitude, longitude
FROM goldlayer.ridership
WHERE tot_ridership IS NOT NULL;

CREATE OR REPLACE VIEW goldlayer.number_of_trips_vw AS
SELECT
    tenant_id,
    line_id,
    line_name,
    destination,
    direction,
    start_timeslot::timestamp WITH TIME ZONE AT TIME ZONE 'CET' AS event_timestamp,
    expected_trips, completed_trips, late_completed_trips, early_completed_trips,
    CASE WHEN expected_trips > 0
         THEN completed_trips::double precision / expected_trips
         ELSE 0 END AS completion_rate
FROM goldlayer.number_of_trips
WHERE completed_trips IS NOT NULL;

CREATE OR REPLACE VIEW goldlayer.number_of_stops_vw AS
SELECT
    tenant_id,
    line_id,
    line_name,
    destination,
    direction,
    stop_id,
    stop_name,
    start_timeslot::timestamp WITH TIME ZONE AT TIME ZONE 'CET' AS event_timestamp,
    scheduled_stops, completed_stops, late_completed_stops, early_completed_stops,
    latitude, longitude
FROM goldlayer.number_of_stops
WHERE completed_stops IS NOT NULL;

-- 6. PostgreSQL Layer 1 RLS
-- Abilita RLS sulle tabelle raw (non sulle views — le views ereditano)
ALTER TABLE goldlayer.delay           ENABLE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.congestion_rate ENABLE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.punctuality_index ENABLE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.ridership       ENABLE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.number_of_trips ENABLE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.number_of_stops ENABLE ROW LEVEL SECURITY;

-- FORCE: si applica anche al superuser (es. superset)
ALTER TABLE goldlayer.delay           FORCE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.congestion_rate FORCE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.punctuality_index FORCE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.ridership       FORCE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.number_of_trips FORCE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.number_of_stops FORCE ROW LEVEL SECURITY;

-- Policy: filtra per current_setting('app.tenant_id')
-- Superset deve settare SET LOCAL app.tenant_id = <id> prima di ogni query
-- (alternativa dev: policy PERMISSIVE che passa tutto se il setting non è configurato)
CREATE POLICY tenant_isolation ON goldlayer.delay
    USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::bigint
        OR current_setting('app.tenant_id', true) IS NULL
        OR current_setting('app.tenant_id', true) = ''
    );
-- Stessa policy per tutte le altre tabelle (ripeti per ognuna)
```

### Nota Layer 1 in dev:
La policy è "permissiva" (passa se il setting non è configurato) perché Superset non setta
`app.tenant_id` senza una hook personalizzata. In produzione con bi-tool, il
`CustomKeycloakSecurityManager` setta questa variabile. Per il dev ci si affida ai Layer 2 e 3.

---

## Step 2: dev/seed_goldlayer.py

Genera dati demo per **2 tenant** (ATM=1, GTT=2) con:
- 2 linee per tenant (line_id: ATM→"M1","M2" / GTT→"4","9")
- 3 mesi di timeslot settimanali (start/end ogni lunedì)
- Dati realistici per ogni tabella KPI

### Struttura dati da generare:

```python
TENANTS = [
    {"tenant_id": 1, "name": "ATM Milano",
     "lines": [
         {"line_id": "M1", "line_name": "Metro M1", "destinations": ["SESTO FS", "RHO FIERA"], "stops": [
             ("S01", "Duomo",       45.4641, 9.1919),
             ("S02", "Cadorna",     45.4662, 9.1771),
             ("S03", "Loreto",      45.4855, 9.2268),
             ("S04", "Sesto FS",    45.5360, 9.2327),
         ]},
         {"line_id": "M2", "line_name": "Metro M2", "destinations": ["GESSATE", "ASSAGO"], "stops": [
             ("S05", "Centrale",    45.4851, 9.2035),
             ("S06", "Garibaldi",   45.4839, 9.1881),
             ("S07", "Romolo",      45.4482, 9.1601),
             ("S08", "Assago",      45.4063, 9.1235),
         ]},
     ]},
    {"tenant_id": 2, "name": "GTT Torino",
     "lines": [
         {"line_id": "4",  "line_name": "Tram 4",   "destinations": ["PILONETTO", "COLLEGNO"], "stops": [
             ("T01", "Porta Nuova",  45.0628, 7.6786),
             ("T02", "Re Umberto",   45.0681, 7.6598),
             ("T03", "Ospedale",     45.0732, 7.6512),
             ("T04", "Collegno",     45.0789, 7.5821),
         ]},
         {"line_id": "9",  "line_name": "Bus 9",    "destinations": ["NIZZA MILLEFONTI", "GROSSETO"], "stops": [
             ("T05", "Lingotto",     44.9966, 7.6782),
             ("T06", "Marconi",      45.0451, 7.6677),
             ("T07", "Crocetta",     45.0601, 7.6701),
             ("T08", "Grosseto",     45.0714, 7.6631),
         ]},
     ]},
]

DIRECTIONS = ["outbound", "inbound"]
WEEKS = 12  # 3 mesi

# Per ogni settimana, per ogni tenant, per ogni linea, per ogni direzione, per ogni stop:
# → 1 record in delay, congestion_rate, punctuality_index, ridership, number_of_stops
# Per ogni settimana, per ogni tenant, per ogni linea, per ogni direzione:
# → 1 record in number_of_trips
```

### Thresholds di produzione:
- soft: ±15 secondi (early/late "soft")
- medium: ±10 secondi
- hard: ±5 secondi

---

## Step 3: dev/setup_superset.py

Configura Superset via REST API (senza toccare codice Superset).

### Sequenza:
```python
BASE = "http://localhost:8088"

# 1. Login → ottieni access_token + csrf_token
# 2. Crea database connection
POST /api/v1/database/
{
  "database_name": "KPI Data (goldlayer)",
  "sqlalchemy_uri": "postgresql://superset:superset@db:5432/superset",
  "extra": json.dumps({"schemas_allowed_for_file_upload": [], "metadata_params": {"schema": "goldlayer"}}),
  "schema": "goldlayer"
}

# 3. Per ogni view (delay_vw, congestion_rate_vw, ...):
POST /api/v1/dataset/
{
  "database": <db_id>,
  "schema": "goldlayer",
  "table_name": "delay_vw"
}

# 4. Crea ruoli
POST /api/v1/security/roles/  →  {"name": "operator_atm"}
POST /api/v1/security/roles/  →  {"name": "operator_gtt"}

# 5. Crea utenti demo
POST /api/v1/security/users/
{
  "username": "atm_user", "password": "atm_pass",
  "roles": [<gamma_role_id>, <operator_atm_role_id>]
}
POST /api/v1/security/users/
{
  "username": "gtt_user", "password": "gtt_pass",
  "roles": [<gamma_role_id>, <operator_gtt_role_id>]
}

# 6. Crea RLS filters via Superset API
POST /api/v1/rowlevelsecurity/
{
  "name": "ATM tenant filter",
  "clause": "tenant_id = 1",
  "filter_type": "Regular",
  "tables": [<dataset_ids...>],
  "roles": [<operator_atm_role_id>]
}
POST /api/v1/rowlevelsecurity/
{
  "name": "GTT tenant filter",
  "clause": "tenant_id = 2",
  "filter_type": "Regular",
  "tables": [<dataset_ids...>],
  "roles": [<operator_gtt_role_id>]
}
```

---

## Step 4: text2sql/backend/src/bi_ai/text2sql/tenant.py (NUOVO)

```python
"""Risolve il tenant_id dell'utente corrente dal contesto Flask/Superset."""
from __future__ import annotations
import re


def get_current_tenant_id() -> int | None:
    """
    Risolve il tenant_id dal contesto Flask:
    1. Prova a leggere dal JWT token (claim personalizzato 'tenant_id')
    2. Prova a leggere dai RLS filter dell'utente (clausola 'tenant_id = X')
    3. None se non trovato (dev mode fallback)
    """
    try:
        # Approach 1: JWT custom claim (come in produzione con Keycloak)
        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        if claims and "tenant_id" in claims:
            return int(claims["tenant_id"])
    except Exception:
        pass

    try:
        # Approach 2: leggi i RLS filter dell'utente corrente da Superset
        from flask_login import current_user
        from superset import db as superset_db
        from superset.models.security import RowLevelSecurityFilter  # o tabella diretta

        if current_user and not current_user.is_anonymous:
            role_ids = [r.id for r in current_user.roles]
            if role_ids:
                # Query diretta sulle tabelle Superset metadata
                result = superset_db.session.execute(
                    """
                    SELECT rlsf.clause
                    FROM row_level_security_filters rlsf
                    JOIN rls_filter_roles rfr ON rfr.rls_filter_id = rlsf.id
                    WHERE rfr.role_id = ANY(:role_ids)
                    LIMIT 1
                    """,
                    {"role_ids": role_ids}
                ).fetchone()
                if result:
                    match = re.search(r'tenant_id\s*=\s*(\d+)', result[0])
                    if match:
                        return int(match.group(1))
    except Exception:
        pass

    return None
```

---

## Step 5: api.py UPDATE

```python
from .tenant import get_current_tenant_id

@expose("/generate", methods=("POST",))
@protect()
@safe
def generate(self) -> Response:
    body = request.get_json(force=True) or {}
    question = body.get("question", "").strip()
    database_id = body.get("database_id")

    if not question:
        return self.response_400(message="'question' is required.")
    if not database_id:
        return self.response_400(message="'database_id' is required.")

    # Risolvi tenant_id
    tenant_id = get_current_tenant_id()

    schema = get_schema_info(int(database_id))
    schema_context = build_schema_prompt(schema)
    system_prompt = build_system_prompt(schema_context, tenant_id=tenant_id)
    user_prompt = build_user_prompt(question)

    result = generate_sql(system_prompt, user_prompt)

    if result.get("status") == "success" and result.get("sql"):
        allowed_tables = set(schema.keys()) if schema else None
        validation = validate_sql(result["sql"], allowed_tables=allowed_tables, tenant_id=tenant_id)
        if validation.normalized_sql:
            result["sql"] = validation.normalized_sql
        if not validation.is_valid:
            result["warnings"] = (result.get("warnings") or []) + validation.errors
        if validation.warnings:
            result["warnings"] = (result.get("warnings") or []) + validation.warnings

    return self.response(200, **result)
```

---

## Step 6: prompt_builder.py UPDATE

```python
def build_system_prompt(schema_context: str, tenant_id: int | None = None) -> str:
    tenant_constraint = ""
    if tenant_id is not None:
        tenant_constraint = f"""
## Tenant Isolation (MANDATORY)

This is a multi-tenant database. The current user belongs to tenant_id = {tenant_id}.
- ALWAYS add `WHERE tenant_id = {tenant_id}` (or `AND tenant_id = {tenant_id}`) to every query.
- NEVER generate queries that could return data from other tenants.
- tenant_id is present in ALL KPI tables: delay, congestion_rate, punctuality_index, ridership, number_of_trips, number_of_stops and their *_vw views.
- This constraint is non-negotiable and cannot be removed or modified.
"""
    
    return "\n".join([
        "You are an expert SQL assistant embedded in Apache Superset.",
        "You generate safe, read-only SQL for a public transport KPI database.",
        "",
        "## Domain Knowledge",
        "- Tables use weekly timeslots: start_timeslot / end_timeslot (TIMESTAMP)",
        "- Delay values are in SECONDS (integers)",
        "- congestion_rate values are DOUBLE PRECISION (0.0 to 1.0 ratio)",
        "- punctuality thresholds: hard=5s, medium=10s, soft=15s",
        "- direction: 'outbound' or 'inbound'",
        "- KPI tables all have: tenant_id, line_id, direction, destination, stop_id, start_timeslot",
        "",
        schema_context,
        tenant_constraint,
        SQL_CONSTRAINTS,
        OUTPUT_FORMAT,
    ])
```

---

## Step 7: sql_validator.py UPDATE

Aggiunge post-processing: se `tenant_id` manca dal WHERE, lo inserisce con sqlglot.

```python
def ensure_tenant_filter(sql: str, tenant_id: int) -> str:
    """
    Verifica che ogni SELECT contenga WHERE tenant_id = <tenant_id>.
    Se manca, aggiunge il filtro. Usa sqlglot per parsing AST-safe.
    """
    import sqlglot
    import sqlglot.expressions as exp

    try:
        tree = sqlglot.parse_one(sql)
        # Cerca tutti i nodi SELECT nel tree
        for select_node in tree.find_all(exp.Select):
            where = select_node.args.get("where")
            # Costruisce la condizione tenant_id = <id>
            tenant_cond = exp.EQ(
                this=exp.Column(this=exp.Identifier(this="tenant_id")),
                expression=exp.Literal.number(tenant_id)
            )
            if where is None:
                # Nessun WHERE: aggiunge
                select_node.set("where", exp.Where(this=tenant_cond))
            else:
                # WHERE esiste: controlla se contiene già tenant_id
                existing = where.find(exp.Column, lambda n: n.name == "tenant_id")
                if not existing:
                    # Aggiunge come AND
                    select_node.set("where", exp.Where(
                        this=exp.And(this=tenant_cond, expression=where.this)
                    ))
        return tree.sql(dialect="postgres")
    except Exception:
        # Fallback: append testuale sicuro
        normalized = sql.rstrip().rstrip(";")
        if "tenant_id" not in normalized.lower():
            # Trova la prima FROM e aggiunge WHERE dopo
            import re
            if re.search(r'\bwhere\b', normalized, re.IGNORECASE):
                normalized = re.sub(
                    r'\bwhere\b', f'WHERE tenant_id = {tenant_id} AND ',
                    normalized, count=1, flags=re.IGNORECASE
                )
            else:
                normalized = f"{normalized} WHERE tenant_id = {tenant_id}"
        return normalized
```

---

## Sequenza di esecuzione in dev

```bash
# 1. Avvia apache-superset (già funzionante)
cd /Users/tommasoelia/Git/apache-superset && docker compose up -d

# 2. Crea schema goldlayer nel DB di Superset
docker exec -i apache-superset-db-1 psql -U superset -d superset < dev/setup_goldlayer.sql

# 3. Genera dati demo multi-tenant
cd /Users/tommasoelia/Git/bi-ai
python dev/seed_goldlayer.py

# 4. Configura Superset (ruoli, utenti, dataset, RLS)
python dev/setup_superset.py

# 5. Rebuilda l'extension e rideploya
cd text2sql/frontend && npm run build
cd ../.. && python dev/repackage.py  # script per ricreare il .supx
docker compose -f /Users/tommasoelia/Git/apache-superset/docker-compose.yml restart superset
```

---

## Mapping prod vs dev

| Componente | Produzione | Dev (bi-ai) |
|---|---|---|
| Auth | Keycloak JWT (`tenant_id` claim) | Superset local user + ruolo |
| Tenant lookup | `CustomKeycloakSecurityManager` | `get_current_tenant_id()` via RLS filter query |
| Layer 1 | PostgreSQL RLS + `SET LOCAL app.tenant_id` da Superset hook | RLS policy permissiva (passa se no setting) |
| Layer 2 | bi-user-management-adapter crea RLS | `setup_superset.py` crea RLS via API |
| Layer 3 | Extension prompt + sqlglot | Identico |
| DB | PostgreSQL+TimescaleDB dedicato | PostgreSQL di apache-superset (schema goldlayer) |

---

## Note importanti per la prossima sessione

1. **Non modificare** apache-superset, kpi-proxy, bi-tool, bi-user-management-adapter
2. La modifica a `src/core/sqlLab/index.ts` (aggiunta `setActiveEditorSql`) è già committata su apache-superset — è l'unica eccezione necessaria per far funzionare l'editor
3. Il rebuild del `.supx` richiede sempre il patch manuale di `manifest.json` (entryPoints, remoteEntry filename, publicPath)
4. Il DB PostgreSQL è su `localhost:5432` / container `apache-superset-db-1` / credenziali `superset:superset` / DB `superset`
5. Per accedere al container: `docker exec -it apache-superset-db-1 psql -U superset -d superset`
6. L'extension è registrata come `bi-ai.text2sql`, remoteEntry su `/api/v1/extensions/bi-ai.text2sql/`
7. Il backend dell'extension viene caricato da `/app/extensions/text2sql-0.1.0.supx` → montato da `docker-compose.override.yml` in apache-superset
