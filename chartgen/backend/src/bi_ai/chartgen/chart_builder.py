"""Assembles form_data and creates Superset ORM objects (SqlaTable + Slice)."""
from __future__ import annotations
import hashlib
import json
import uuid
from datetime import datetime

VALID_VIZ_TYPES = {
    "echarts_timeseries_line", "echarts_timeseries_bar", "echarts_bar",
    "pie", "table", "big_number_total",
}


def _adhoc_metric(col_name: str, label: str | None = None) -> dict:
    return {
        "expressionType": "SQL",
        "sqlExpression": f"SUM({col_name})",
        "label": label or f"SUM({col_name})",
        "hasCustomLabel": bool(label),
        "aggregate": None,
        "column": None,
        "isNew": False,
        "optionName": f"metric_{col_name}",
    }


def _adhoc_filter(sql_expression: str) -> dict:
    return {
        "expressionType": "SQL",
        "clause": "WHERE",
        "sqlExpression": sql_expression,
        "filterOptionName": f"filter_{uuid.uuid4().hex[:8]}",
        "isExtra": False,
        "isNew": False,
    }


def _build_form_data(viz_type: str, suggestion: dict, datasource_id: int, dataset=None) -> dict:
    datasource = f"{datasource_id}__table"

    # Convert LLM adhoc_filters (list of SQL strings) to Superset format
    raw_filters = suggestion.get("adhoc_filters", [])
    filters = [_adhoc_filter(f) for f in raw_filters if f]

    base = {
        "datasource": datasource,
        "viz_type": viz_type,
        "adhoc_filters": filters,
        "row_limit": 10000,
        "color_scheme": "supersetColors",
        "show_legend": True,
    }

    # Physical dataset (sql=None): use LLM metrics/axes directly — they reference raw columns
    # Virtual dataset (sql set): introspect actual output columns
    use_llm_directly = dataset is None or getattr(dataset, "sql", None) is None

    if use_llm_directly:
        metrics = suggestion.get("metrics", [])
        group_by = suggestion.get("group_by", [])
        x_axis = suggestion.get("x_axis")
        all_col_names = [c.column_name for c in dataset.columns] if dataset else []

        # LLM x_axis may reference a SQL alias (e.g. "date") that doesn't exist
        # in the physical dataset — remap to the nearest real column
        if dataset is not None and x_axis not in all_col_names:
            time_cols = [c.column_name for c in dataset.columns if c.is_temporal]
            str_cols = [c.column_name for c in dataset.columns if not c.is_numeric and not c.is_temporal]
            if viz_type == "echarts_timeseries_line" and time_cols:
                x_axis = time_cols[0]
            elif str_cols:
                x_axis = str_cols[0]
            elif all_col_names:
                x_axis = all_col_names[0]

        # Drop any group_by entries that reference SQL aliases not in the dataset
        if all_col_names:
            group_by = [c for c in group_by if c in all_col_names]
    else:
        str_cols = [c.column_name for c in dataset.columns if not c.is_numeric and not c.is_temporal]
        num_cols = [c.column_name for c in dataset.columns if c.is_numeric]
        time_cols = [c.column_name for c in dataset.columns if c.is_temporal]
        all_col_names = [c.column_name for c in dataset.columns]

        llm_metrics = suggestion.get("metrics", [])
        metrics = [
            _adhoc_metric(col, llm_metrics[i].get("label") if i < len(llm_metrics) else None)
            for i, col in enumerate(num_cols)
        ]

        llm_x = suggestion.get("x_axis")
        if llm_x in all_col_names:
            x_axis = llm_x
        elif str_cols:
            x_axis = str_cols[0]
        elif time_cols:
            x_axis = time_cols[0]
        else:
            x_axis = all_col_names[0] if all_col_names else None

        llm_group_by = suggestion.get("group_by", [])
        group_by = [c for c in llm_group_by if c in all_col_names and c != x_axis]

        if viz_type == "echarts_timeseries_line" and time_cols:
            x_axis = llm_x if llm_x in time_cols else time_cols[0]

    time_grain = suggestion.get("time_grain_sqla", "P1D")

    if viz_type == "echarts_timeseries_line":
        return {**base, "granularity_sqla": x_axis, "time_grain_sqla": time_grain,
                "time_range": "No filter", "metrics": metrics, "groupby": group_by}

    if viz_type in ("echarts_timeseries_bar", "echarts_bar"):
        return {**base, "metrics": metrics, "groupby": group_by,
                "x_axis": x_axis or (group_by[0] if group_by else None), "time_range": "No filter"}

    if viz_type == "pie":
        return {**base, "metric": metrics[0] if metrics else None,
                "groupby": group_by or ([x_axis] if x_axis else [])}

    if viz_type == "big_number_total":
        return {**base, "metric": metrics[0] if metrics else None, "time_range": "No filter"}

    # table
    return {**base, "all_columns": all_col_names, "order_by_cols": []}


def _find_existing_dataset(db, SqlaTable, source_table: str | None, database_id: int):
    """Look up a registered physical dataset by schema.table_name."""
    if not source_table or "." not in source_table:
        return None
    schema, table_name = source_table.split(".", 1)
    return db.session.query(SqlaTable).filter_by(
        database_id=database_id,
        schema=schema,
        table_name=table_name,
        sql=None,
    ).first()


def create_chart(sql: str, database_id: int, suggestion: dict) -> dict:
    """Create a chart in Superset, reusing an existing shared dataset when possible."""
    from superset import db
    from superset.connectors.sqla.models import SqlaTable
    from superset.models.slice import Slice
    from flask_login import current_user

    viz_type = suggestion.get("viz_type", "table")
    if viz_type not in VALID_VIZ_TYPES:
        viz_type = "table"

    title = suggestion.get("title") or f"AI Chart {datetime.now().strftime('%H:%M')}"
    owner_id = getattr(current_user, "id", None)

    # Try to reuse a registered physical dataset (enables dashboard filter sharing)
    source_table = suggestion.get("source_table")
    dataset = _find_existing_dataset(db, SqlaTable, source_table, database_id)

    if dataset is None:
        # Virtual dataset — the SQL already embeds WHERE conditions.
        # adhoc_filters would reference columns absent from the SELECT output,
        # causing "column does not exist" in Superset Explore.
        suggestion = {**suggestion, "adhoc_filters": []}

        # Fallback: create a virtual dataset from the SQL
        sql_hash = hashlib.md5(sql.encode()).hexdigest()[:8]
        dataset_name = f"{title[:60]} [{sql_hash}]"

        dataset = db.session.query(SqlaTable).filter_by(
            database_id=database_id, schema="goldlayer", table_name=dataset_name
        ).first()

        if dataset is None:
            dataset = SqlaTable(
                table_name=dataset_name,
                sql=sql,
                database_id=database_id,
                schema="goldlayer",
                is_sqllab_view=True,
            )
            if owner_id:
                dataset.owners = [current_user]
            db.session.add(dataset)
            db.session.flush()
            try:
                dataset.fetch_metadata()
            except Exception:
                pass

    form_data = _build_form_data(viz_type, suggestion, dataset.id, dataset=dataset)

    chart = Slice(
        slice_name=title,
        datasource_id=dataset.id,
        datasource_type="table",
        viz_type=viz_type,
        params=json.dumps(form_data),
    )
    if owner_id:
        chart.created_by_fk = owner_id
    db.session.add(chart)
    db.session.commit()

    return {"chart_id": chart.id, "explore_url": f"/explore/?slice_id={chart.id}"}
