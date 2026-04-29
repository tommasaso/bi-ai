-- Setup goldlayer schema in Superset PostgreSQL
-- Run: docker exec -i apache-superset-db-1 psql -U superset -d superset < dev/setup_goldlayer.sql

CREATE SCHEMA IF NOT EXISTS goldlayer;

-- Tenant registry
CREATE TABLE IF NOT EXISTS goldlayer.operator (
    id                 BIGINT PRIMARY KEY,
    tenant_id          BIGINT NOT NULL UNIQUE,
    name               VARCHAR NOT NULL,
    lang               VARCHAR,
    timezone           VARCHAR,
    creation_timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);
INSERT INTO goldlayer.operator (id, tenant_id, name, lang, timezone, creation_timestamp) VALUES
    (1, 1, 'ATM Milano', 'it', 'Europe/Rome', NOW()),
    (2, 2, 'GTT Torino', 'it', 'Europe/Rome', NOW())
ON CONFLICT DO NOTHING;

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

-- KPI tables (schema from kpi-proxy 0.0.1.1)
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

-- Views (from kpi-proxy 0.0.1.3)
CREATE OR REPLACE VIEW goldlayer.delay_vw AS
SELECT
    tenant_id,
    line_id,
    line_name,
    destination,
    direction,
    stop_id,
    stop_name,
    start_timeslot AT TIME ZONE 'CET' AS event_timestamp,
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
    start_timeslot AT TIME ZONE 'CET' AS event_timestamp,
    CASE
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 7  AND EXTRACT(hour FROM start_timeslot)::int < 9  THEN 0
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 9  AND EXTRACT(hour FROM start_timeslot)::int < 16 THEN 1
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 16 AND EXTRACT(hour FROM start_timeslot)::int < 19 THEN 2
        WHEN EXTRACT(hour FROM start_timeslot)::int >= 19 AND EXTRACT(hour FROM start_timeslot)::int < 24 THEN 3
        ELSE 4
    END AS peaks,
    GREATEST(0, min_value)      AS min_congestion_rate,
    GREATEST(0, max_value)      AS max_congestion_rate,
    GREATEST(0, mean_value)     AS mean_congestion_rate,
    GREATEST(0, dev_std_value)  AS dev_std_congestion_rate,
    latitude, longitude
FROM goldlayer.congestion_rate
WHERE min_value IS NOT NULL;

CREATE OR REPLACE VIEW goldlayer.punctuality_index_vw AS
WITH base AS (
    SELECT *,
           start_timeslot AT TIME ZONE 'CET' AS event_timestamp
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
    start_timeslot AT TIME ZONE 'CET' AS event_timestamp,
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
    start_timeslot AT TIME ZONE 'CET' AS event_timestamp,
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
    start_timeslot AT TIME ZONE 'CET' AS event_timestamp,
    scheduled_stops, completed_stops, late_completed_stops, early_completed_stops,
    latitude, longitude
FROM goldlayer.number_of_stops
WHERE completed_stops IS NOT NULL;

-- Layer 1: PostgreSQL RLS policies
ALTER TABLE goldlayer.delay             ENABLE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.congestion_rate   ENABLE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.punctuality_index ENABLE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.ridership         ENABLE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.number_of_trips   ENABLE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.number_of_stops   ENABLE ROW LEVEL SECURITY;

ALTER TABLE goldlayer.delay             FORCE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.congestion_rate   FORCE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.punctuality_index FORCE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.ridership         FORCE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.number_of_trips   FORCE ROW LEVEL SECURITY;
ALTER TABLE goldlayer.number_of_stops   FORCE ROW LEVEL SECURITY;

-- Permissive policy in dev: passes if app.tenant_id is not set
-- In production, bi-tool's security manager sets SET LOCAL app.tenant_id = X
DROP POLICY IF EXISTS tenant_isolation ON goldlayer.delay;
CREATE POLICY tenant_isolation ON goldlayer.delay
    USING (
        current_setting('app.tenant_id', true) IS NULL
        OR current_setting('app.tenant_id', true) = ''
        OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::bigint
    );

DROP POLICY IF EXISTS tenant_isolation ON goldlayer.congestion_rate;
CREATE POLICY tenant_isolation ON goldlayer.congestion_rate
    USING (
        current_setting('app.tenant_id', true) IS NULL
        OR current_setting('app.tenant_id', true) = ''
        OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::bigint
    );

DROP POLICY IF EXISTS tenant_isolation ON goldlayer.punctuality_index;
CREATE POLICY tenant_isolation ON goldlayer.punctuality_index
    USING (
        current_setting('app.tenant_id', true) IS NULL
        OR current_setting('app.tenant_id', true) = ''
        OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::bigint
    );

DROP POLICY IF EXISTS tenant_isolation ON goldlayer.ridership;
CREATE POLICY tenant_isolation ON goldlayer.ridership
    USING (
        current_setting('app.tenant_id', true) IS NULL
        OR current_setting('app.tenant_id', true) = ''
        OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::bigint
    );

DROP POLICY IF EXISTS tenant_isolation ON goldlayer.number_of_trips;
CREATE POLICY tenant_isolation ON goldlayer.number_of_trips
    USING (
        current_setting('app.tenant_id', true) IS NULL
        OR current_setting('app.tenant_id', true) = ''
        OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::bigint
    );

DROP POLICY IF EXISTS tenant_isolation ON goldlayer.number_of_stops;
CREATE POLICY tenant_isolation ON goldlayer.number_of_stops
    USING (
        current_setting('app.tenant_id', true) IS NULL
        OR current_setting('app.tenant_id', true) = ''
        OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::bigint
    );
