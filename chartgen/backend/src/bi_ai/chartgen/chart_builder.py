"""Assembles form_data and creates Superset ORM objects (SqlaTable + Slice)."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime

VALID_VIZ_TYPES = {"echarts_timeseries_line", "echarts_bar", "pie", "table", "big_number_total"}


def _build_form_data(viz_type: str, suggestion: dict, datasource_id: int) -> dict:
    datasource = f"{datasource_id}__table"
    base = {
        "datasource": datasource,
        "viz_type": viz_type,
        "adhoc_filters": [],
        "row_limit": 10000,
        "color_scheme": "supersetColors",
        "show_legend": True,
    }
    metrics = suggestion.get("metrics", [])
    group_by = suggestion.get("group_by", [])
    x_axis = suggestion.get("x_axis")
    time_grain = suggestion.get("time_grain_sqla", "P1D")

    if viz_type == "echarts_timeseries_line":
        return {**base, "granularity_sqla": x_axis, "time_grain_sqla": time_grain,
                "time_range": "No filter", "metrics": metrics, "groupby": group_by}

    if viz_type == "echarts_bar":
        return {**base, "metrics": metrics, "groupby": group_by,
                "x_axis": x_axis or (group_by[0] if group_by else None), "time_range": "No filter"}

    if viz_type == "pie":
        return {**base, "metric": metrics[0] if metrics else None, "groupby": group_by}

    if viz_type == "big_number_total":
        return {**base, "metric": metrics[0] if metrics else None, "time_range": "No filter"}

    # table (default)
    return {**base, "all_columns": [], "order_by_cols": []}


def create_chart(sql: str, database_id: int, suggestion: dict) -> dict:
    """Create virtual dataset + chart via Superset ORM. Returns explore_url."""
    from superset import db
    from superset.connectors.sqla.models import SqlaTable
    from superset.models.slice import Slice
    from flask_login import current_user

    viz_type = suggestion.get("viz_type", "table")
    if viz_type not in VALID_VIZ_TYPES:
        viz_type = "table"

    title = suggestion.get("title") or f"AI Chart {datetime.now().strftime('%H:%M')}"
    sql_hash = hashlib.md5(sql.encode()).hexdigest()[:8]
    dataset_name = f"{title[:60]} [{sql_hash}]"

    owner_id = getattr(current_user, "id", None)

    dataset = SqlaTable(
        table_name=dataset_name,
        sql=sql,
        database_id=database_id,
        schema="goldlayer",
    )
    if owner_id:
        dataset.owners = [current_user]
    db.session.add(dataset)
    db.session.flush()

    form_data = _build_form_data(viz_type, suggestion, dataset.id)

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
