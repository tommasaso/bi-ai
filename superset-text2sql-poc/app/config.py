import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openrouter")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen/qwen3.5-coder")
    OPENROUTER_HTTP_REFERER: str = os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost:8501")
    OPENROUTER_X_TITLE: str = os.getenv("OPENROUTER_X_TITLE", "Superset Text-to-SQL PoC")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./demo_transport.db")

    def validate(self) -> list[str]:
        errors = []
        if not self.LLM_API_KEY or self.LLM_API_KEY == "your_openrouter_api_key_here":
            errors.append("LLM_API_KEY is not set. Please configure it in .env file.")
        return errors


settings = Settings()
