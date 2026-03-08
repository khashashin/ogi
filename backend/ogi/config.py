import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="OGI_")

    app_name: str = "OGI"

    # Supabase
    supabase_url: str = os.environ.get("OGI_SUPABASE_URL", "")
    supabase_anon_key: str = os.environ.get("OGI_SUPABASE_ANON_KEY", "")
    supabase_service_role_key: str = os.environ.get("OGI_SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_jwt_secret: str = os.environ.get("OGI_SUPABASE_JWT_SECRET", "")

    # Direct PostgreSQL (asyncpg)
    database_url: str = os.environ.get("OGI_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ogi")

    # Plugins
    plugin_dirs: list[str] = ["plugins"]

    # SQLite (default for local dev; set OGI_USE_SQLITE=false for PostgreSQL)
    database_path: str = os.environ.get("OGI_DB_PATH", "ogi.db")
    use_sqlite: bool = os.environ.get("OGI_USE_SQLITE", True)

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    host: str = os.environ.get("OGI_HOST", "0.0.0.0")
    port: int = os.environ.get("OGI_PORT", 8000)

    @property
    def abs_database_path(self) -> Path:
        return Path(self.database_path).resolve()


settings = Settings()
