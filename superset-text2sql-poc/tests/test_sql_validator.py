import pytest
from app.sql_validator import validate_sql

ALLOWED = {"lines", "trips", "stop_events", "vehicle_events", "passenger_counts"}


def test_valid_select():
    sql = "SELECT line_id, AVG(arrival_delay_seconds) FROM stop_events GROUP BY line_id LIMIT 10"
    result = validate_sql(sql, ALLOWED)
    assert result.is_valid


def test_drop_table_blocked():
    sql = "DROP TABLE stop_events"
    result = validate_sql(sql, ALLOWED)
    assert not result.is_valid
    assert any("Only SELECT" in e or "Forbidden" in e for e in result.errors)


def test_delete_blocked():
    sql = "DELETE FROM stop_events WHERE trip_id = 1"
    result = validate_sql(sql, ALLOWED)
    assert not result.is_valid


def test_multiple_statements_blocked():
    sql = "SELECT 1; DROP TABLE stop_events"
    result = validate_sql(sql, ALLOWED)
    assert not result.is_valid
    assert any("Multiple" in e for e in result.errors)


def test_unknown_table_blocked():
    sql = "SELECT * FROM nonexistent_table LIMIT 10"
    result = validate_sql(sql, ALLOWED)
    assert not result.is_valid
    assert any("unknown table" in e.lower() for e in result.errors)


def test_missing_limit_warns():
    sql = "SELECT line_id FROM lines"
    result = validate_sql(sql, ALLOWED)
    assert any("LIMIT" in w for w in result.warnings)


def test_with_cte_allowed():
    sql = "WITH avg_delay AS (SELECT line_id, AVG(arrival_delay_seconds) AS avg_d FROM stop_events GROUP BY line_id) SELECT * FROM avg_delay LIMIT 10"
    result = validate_sql(sql, ALLOWED)
    assert result.is_valid


def test_insert_blocked():
    sql = "INSERT INTO lines (line_name) VALUES ('test')"
    result = validate_sql(sql, ALLOWED)
    assert not result.is_valid
