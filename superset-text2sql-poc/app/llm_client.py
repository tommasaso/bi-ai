import json
import re
from openai import OpenAI, APIConnectionError, AuthenticationError, APIStatusError
from app.config import settings


def get_client() -> OpenAI:
    return OpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        default_headers={
            "HTTP-Referer": settings.OPENROUTER_HTTP_REFERER,
            "X-Title": settings.OPENROUTER_X_TITLE,
        },
    )


def _extract_json(text: str) -> dict:
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(cleaned)


def generate_sql(system_prompt: str, user_prompt: str) -> dict:
    errors = settings.validate()
    if errors:
        return {
            "status": "error",
            "sql": "",
            "explanation": errors[0],
            "used_tables": [],
            "used_columns": [],
            "assumptions": [],
            "warnings": [],
        }

    client = get_client()

    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        raw = response.choices[0].message.content or ""
        result = _extract_json(raw)

        for field in ("status", "sql", "explanation", "used_tables", "used_columns", "assumptions", "warnings"):
            if field not in result:
                result[field] = [] if field in ("used_tables", "used_columns", "assumptions", "warnings") else ""

        return result

    except AuthenticationError:
        return _error_response("Authentication failed. Check your LLM_API_KEY.")
    except APIConnectionError:
        return _error_response("Cannot connect to LLM provider. Check LLM_BASE_URL and network.")
    except APIStatusError as e:
        return _error_response(f"LLM API error {e.status_code}: {e.message}")
    except json.JSONDecodeError:
        return _error_response(f"LLM returned non-JSON response: {raw[:200]}")
    except Exception as e:
        return _error_response(f"Unexpected error: {str(e)}")


def _error_response(message: str) -> dict:
    return {
        "status": "error",
        "sql": "",
        "explanation": message,
        "used_tables": [],
        "used_columns": [],
        "assumptions": [],
        "warnings": [],
    }
