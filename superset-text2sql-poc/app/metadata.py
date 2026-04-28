from sqlalchemy import inspect, text
from app.database import get_engine

TABLE_DESCRIPTIONS = {
    "lines": "Public transport lines with their mode (bus, tram, metro, trolleybus) and operator.",
    "trips": "Individual trips operated on a line for a given service date, including scheduled and actual start/end times and trip status.",
    "stop_events": "Arrival events at each stop for a trip, including scheduled and actual arrival times and computed arrival delay in seconds.",
    "vehicle_events": "Operational anomaly events for vehicles (diagnostic alarms, GPS loss, door failures, etc.) with severity.",
    "passenger_counts": "Passenger boarding and alighting counts recorded for a vehicle on a line at a given timestamp.",
}

COLUMN_DESCRIPTIONS = {
    "lines": {
        "line_id": "Primary key, unique line identifier.",
        "line_name": "Human-readable line name (e.g. 'Line 1', 'Line M1').",
        "mode": "Transport mode: bus, tram, metro, trolleybus.",
        "operator_name": "Name of the operating company.",
    },
    "trips": {
        "trip_id": "Primary key, unique trip identifier.",
        "line_id": "Foreign key to lines.line_id.",
        "service_date": "Date on which the trip was operated (YYYY-MM-DD).",
        "direction": "Trip direction: outbound or inbound.",
        "scheduled_start_time": "Planned departure datetime.",
        "actual_start_time": "Actual departure datetime.",
        "scheduled_end_time": "Planned arrival at terminus datetime.",
        "actual_end_time": "Actual arrival at terminus datetime.",
        "status": "Trip status: completed, cancelled, delayed.",
    },
    "stop_events": {
        "event_id": "Primary key.",
        "trip_id": "Foreign key to trips.trip_id.",
        "line_id": "Foreign key to lines.line_id.",
        "stop_id": "Stop identifier.",
        "service_date": "Service date for this stop event (YYYY-MM-DD).",
        "scheduled_arrival_time": "Planned arrival datetime at this stop.",
        "actual_arrival_time": "Actual arrival datetime at this stop.",
        "arrival_delay_seconds": "Delay in seconds (actual minus scheduled). Negative means early.",
    },
    "vehicle_events": {
        "event_id": "Primary key.",
        "vehicle_id": "Vehicle identifier.",
        "line_id": "Foreign key to lines.line_id.",
        "event_timestamp": "Datetime of the event.",
        "event_type": "Type of anomaly: diagnostic_alarm, communication_loss, gps_loss, door_failure.",
        "severity": "Severity level: low, medium, high, critical.",
    },
    "passenger_counts": {
        "count_id": "Primary key.",
        "line_id": "Foreign key to lines.line_id.",
        "vehicle_id": "Vehicle identifier.",
        "event_timestamp": "Datetime of the count recording.",
        "boarding_count": "Number of passengers who boarded.",
        "alighting_count": "Number of passengers who alighted.",
        "occupancy": "Total passengers on board at the time of recording.",
    },
}


def get_schema_metadata() -> dict:
    engine = get_engine()
    inspector = inspect(engine)
    schema = {}
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        fks = inspector.get_foreign_keys(table_name)
        schema[table_name] = {
            "columns": [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "description": COLUMN_DESCRIPTIONS.get(table_name, {}).get(col["name"], ""),
                }
                for col in columns
            ],
            "foreign_keys": [
                {
                    "constrained_columns": fk["constrained_columns"],
                    "referred_table": fk["referred_table"],
                    "referred_columns": fk["referred_columns"],
                }
                for fk in fks
            ],
            "description": TABLE_DESCRIPTIONS.get(table_name, ""),
        }
    return schema


def build_metadata_context(schema: dict) -> str:
    lines = ["## Database Schema\n"]
    for table_name, info in schema.items():
        lines.append(f"### Table: `{table_name}`")
        lines.append(f"Description: {info['description']}\n")
        lines.append("Columns:")
        for col in info["columns"]:
            desc = f" — {col['description']}" if col["description"] else ""
            lines.append(f"  - `{col['name']}` ({col['type']}){desc}")
        if info["foreign_keys"]:
            lines.append("\nForeign keys:")
            for fk in info["foreign_keys"]:
                lines.append(f"  - {fk['constrained_columns']} → {fk['referred_table']}.{fk['referred_columns']}")
        lines.append("")
    return "\n".join(lines)
