from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved relative to this file, not the process's working directory --
# uvicorn can be launched from the repo root or from backend/ depending on
# how it's started, and a plain ".env" would silently miss the real file
# (and fall back to the sqlite default) whenever the cwd doesn't match.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # Default a SQLite file for local/dev — no Docker/Postgres available in this
    # environment (see PROGRESS.md). Production must set DATABASE_URL to a real
    # Postgres DSN per docs/architecture/PLANNING.md and ADR 0001.
    database_url: str = "sqlite:///./contractor.db"
    api_key_header_name: str = "X-API-Key"
    cors_allow_origins: list[str] = ["http://localhost:3000"]

    # Optional: BazaarLink (bazaarlink.ai), an OpenAI-compatible AI gateway --
    # see ADR 0002 and app/ai.py. Narrative generation degrades to
    # unavailable, never simulated, when this isn't set.
    bazaarlink_api_key: str | None = None


settings = Settings()
