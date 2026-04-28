from flask import request, Response
from flask_appbuilder.api import expose, protect, safe
from superset_core.api.rest_api import RestApi, add_extension_api

from .llm import generate_sql
from .metadata import get_schema_info, build_schema_prompt
from .prompt_builder import build_system_prompt, build_user_prompt
from .sql_validator import validate_sql


class Text2SqlAPI(RestApi):
    resource_name = "bi-ai/text2sql"

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

        schema = get_schema_info(int(database_id))
        schema_context = build_schema_prompt(schema)
        system_prompt = build_system_prompt(schema_context)
        user_prompt = build_user_prompt(question)

        result = generate_sql(system_prompt, user_prompt)

        if result.get("status") == "success" and result.get("sql"):
            allowed_tables = set(schema.keys()) if schema else None
            validation = validate_sql(result["sql"], allowed_tables=allowed_tables)
            if validation.normalized_sql:
                result["sql"] = validation.normalized_sql
            if not validation.is_valid:
                result["warnings"] = (result.get("warnings") or []) + validation.errors
            if validation.warnings:
                result["warnings"] = (result.get("warnings") or []) + validation.warnings

        return self.response(200, **result)


add_extension_api(Text2SqlAPI)
