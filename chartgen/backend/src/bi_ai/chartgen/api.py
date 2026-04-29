from flask import request, Response
from flask_appbuilder.api import expose, protect, safe
from superset_core.api.rest_api import RestApi, add_extension_api

from .chart_llm import suggest_chart
from .chart_builder import create_chart


class ChartGenAPI(RestApi):
    resource_name = "bi-ai/chartgen"

    @expose("/suggest", methods=("POST",))
    @protect()
    @safe
    def suggest(self) -> Response:
        body = request.get_json(force=True) or {}
        sql = body.get("sql", "").strip()
        columns = body.get("columns", [])
        question = body.get("question", "").strip()

        if not sql:
            return self.response_400(message="'sql' is required.")

        result = suggest_chart(sql, columns, question)
        return self.response(200, **result)

    @expose("/create", methods=("POST",))
    @protect()
    @safe
    def create(self) -> Response:
        body = request.get_json(force=True) or {}
        sql = body.get("sql", "").strip()
        database_id = body.get("database_id")
        suggestion = body.get("suggestion", {})

        if not sql:
            return self.response_400(message="'sql' is required.")
        if not database_id:
            return self.response_400(message="'database_id' is required.")

        try:
            result = create_chart(sql, int(database_id), suggestion)
            return self.response(200, **result)
        except Exception as e:
            return self.response(500, error=str(e))


add_extension_api(ChartGenAPI)
