import json
import os
import re
from openai import OpenAI, APIConnectionError, AuthenticationError, APIStatusError


def _get_client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=os.environ["LLM_API_KEY"],
        default_headers={
            "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER", "https://github.com/tommasaso/bi-ai"),
            "X-Title": os.environ.get("OPENROUTER_X_TITLE", "BI-AI Text-to-SQL"),
        },
    )


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(cleaned)


def generate_sql(system_prompt: str, user_prompt: str) -> dict:
    client = _get_client()
    model = os.environ.get("LLM_MODEL", "qwen/qwen3-coder")
    try:
        response = client.chat.completions.create(
            model=model,
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
        return _err("Authentication failed. Check LLM_API_KEY.")
    except APIConnectionError:
        return _err("Cannot connect to LLM provider. Check LLM_BASE_URL and network.")
    except APIStatusError as e:
        return _err(f"LLM API error {e.status_code}: {e.message}")
    except json.JSONDecodeError:
        raw_preview = locals().get("raw", "")[:200]
        return _err(f"LLM returned non-JSON response: {raw_preview}")
    except Exception as e:
        return _err(f"Unexpected error: {str(e)}")


def _err(message: str) -> dict:
    return {
        "status": "error",
        "sql": "",
        "explanation": message,
        "used_tables": [],
        "used_columns": [],
        "assumptions": [],
        "warnings": [],
    }
