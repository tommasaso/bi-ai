"""Schema introspection via Superset's Database model."""
from __future__ import annotations


GOLDLAYER_SCHEMA = "goldlayer"

# Views are the public API for queries; raw tables are for reference only
PREFERRED_VIEWS = [
    "delay_vw",
    "congestion_rate_vw",
    "punctuality_index_vw",
    "ridership_vw",
    "number_of_trips_vw",
    "number_of_stops_vw",
]


def get_schema_info(database_id: int) -> dict:
    try:
        from superset.models.core import Database  # type: ignore[import]
        from superset import db as superset_db  # type: ignore[import]

        database = superset_db.session.get(Database, database_id)
        if database is None:
            return {}

        with database.get_inspector() as inspector:
            return _inspect(inspector, schema=GOLDLAYER_SCHEMA)

    except ImportError:
        import os
        from sqlalchemy import create_engine, inspect as sa_inspect
        url = os.environ.get("DATABASE_URL", "sqlite:///demo_transport.db")
        engine = create_engine(url)
        return _inspect(sa_inspect(engine))


def _inspect(inspector, schema: str | None = None) -> dict:
    result: dict = {}

    try:
        view_names = inspector.get_view_names(schema=schema)
    except Exception:
        view_names = []

    try:
        table_names = inspector.get_table_names(schema=schema)
    except Exception:
        table_names = []

    # Views first (preferred for queries), then raw tables
    all_names = [(n, "view") for n in view_names] + [(n, "table") for n in table_names]

    for obj_name, obj_type in all_names:
        try:
            columns = inspector.get_columns(obj_name, schema=schema)
        except Exception:
            columns = []
        try:
            fks = inspector.get_foreign_keys(obj_name, schema=schema) if obj_type == "table" else []
        except Exception:
            fks = []

        qualified = f"{schema}.{obj_name}" if schema else obj_name
        result[qualified] = {
            "type": obj_type,
            "columns": [{"name": c["name"], "type": str(c["type"])} for c in columns],
            "foreign_keys": [
                {
                    "constrained_columns": fk["constrained_columns"],
                    "referred_table": fk["referred_table"],
                    "referred_columns": fk["referred_columns"],
                }
                for fk in fks
            ],
        }
    return result


def build_schema_prompt(schema: dict) -> str:
    lines = ["## Available Schema\n"]
    # Views first
    for name, info in schema.items():
        if info.get("type") != "view":
            continue
        lines.append(f"### View: `{name}` (use this for queries)")
        for col in info["columns"]:
            lines.append(f"  - `{col['name']}` ({col['type']})")
        lines.append("")
    # Raw tables (for reference)
    for name, info in schema.items():
        if info.get("type") != "table":
            continue
        lines.append(f"### Table: `{name}` (raw — prefer *_vw views when available)")
        for col in info["columns"]:
            lines.append(f"  - `{col['name']}` ({col['type']})")
        lines.append("")
    return "\n".join(lines)
