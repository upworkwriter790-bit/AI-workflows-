from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/resume_builder"

    # Auth / JWT
    jwt_secret: str = "change-me-in-.env-this-is-not-secure"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Frontend origin (for CORS + OAuth redirects)
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    # Google OAuth (Google Cloud Console > APIs & Services > Credentials)
    google_client_id: str | None = None
    google_client_secret: str | None = None

    # GitHub OAuth (GitHub > Settings > Developer settings > OAuth Apps)
    github_client_id: str | None = None
    github_client_secret: str | None = None

    # Local file storage for uploaded resumes
    upload_dir: str = "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
