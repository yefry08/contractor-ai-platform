from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Default a SQLite file for local/dev — no Docker/Postgres available in this
    # environment (see PROGRESS.md). Production must set DATABASE_URL to a real
    # Postgres DSN per docs/architecture/PLANNING.md and ADR 0001.
    database_url: str = "sqlite:///./contractor.db"
    api_key_header_name: str = "X-API-Key"
    cors_allow_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
