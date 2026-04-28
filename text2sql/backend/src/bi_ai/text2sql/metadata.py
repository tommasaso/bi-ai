"""Schema introspection via Superset's Database model."""
from __future__ import annotations


def get_schema_info(database_id: int) -> dict:
    try:
        from superset.models.core import Database  # type: ignore[import]
        from superset import db as superset_db  # type: ignore[import]

        database = superset_db.session.get(Database, database_id)
        if database is None:
            return {}

        with database.get_inspector() as inspector:
            return _inspect(inspector)

    except ImportError:
        import os
        from sqlalchemy import create_engine, inspect as sa_inspect
        url = os.environ.get("DATABASE_URL", "sqlite:///demo_transport.db")
        engine = create_engine(url)
        return _inspect(sa_inspect(engine))


def _inspect(inspector) -> dict:
    schema: dict = {}
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        fks = inspector.get_foreign_keys(table_name)
        schema[table_name] = {
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
    return schema


def build_schema_prompt(schema: dict) -> str:
    lines = ["## Database Schema\n"]
    for table_name, info in schema.items():
        lines.append(f"### Table: `{table_name}`")
        lines.append("Columns:")
        for col in info["columns"]:
            lines.append(f"  - `{col['name']}` ({col['type']})")
        if info["foreign_keys"]:
            lines.append("Foreign keys:")
            for fk in info["foreign_keys"]:
                lines.append(f"  - {fk['constrained_columns']} → {fk['referred_table']}.{fk['referred_columns']}")
        lines.append("")
    return "\n".join(lines)
