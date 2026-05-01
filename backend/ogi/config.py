import os
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_prefix="OGI_", extra="ignore")

    app_name: str = "OGI"

    # Supabase
    supabase_url: str = os.environ.get("OGI_SUPABASE_URL", "")
    supabase_anon_key: str = os.environ.get("OGI_SUPABASE_ANON_KEY", "")
    supabase_service_role_key: str = os.environ.get("OGI_SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_jwt_secret: str = os.environ.get("OGI_SUPABASE_JWT_SECRET", "")

    # Direct PostgreSQL (asyncpg)
    database_url: str = os.environ.get("OGI_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ogi")

    # Plugins
    plugin_dirs: list[str] = ["plugins", "../plugins"]

    # SQLite (default for local dev; set OGI_USE_SQLITE=false for PostgreSQL)
    database_path: str = os.environ.get("OGI_DB_PATH", "ogi.db")
    use_sqlite: bool = os.environ.get("OGI_USE_SQLITE", True)

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    host: str = os.environ.get("OGI_HOST", "0.0.0.0")
    port: int = os.environ.get("OGI_PORT", 8000)

    # Deployment mode
    deployment_mode: str = "self-hosted"  # "cloud" | "self-hosted"

    # Transform Hub / Registry
    registry_repo: str = "opengraphintel/ogi-transforms"
    registry_cache_ttl: int = 3600  # seconds
    # TODO: Remove after official launch and the repository is public
    github_token: str | None = os.environ.get("OGI_GITHUB_TOKEN", None)
    api_key_encryption_key: str | None = os.environ.get("OGI_API_KEY_ENCRYPTION_KEY", None)
    admin_emails: str = ""
    expose_error_details: bool = False

    @field_validator("admin_emails", mode="before")
    @classmethod
    def _parse_admin_emails(cls, v: object) -> str:
        if isinstance(v, list):
            return ",".join(str(i) for i in v)
        return str(v) if v else ""

    @field_validator(
        "plugin_dirs",
        "cors_origins",
        "sandbox_allowed_tiers",
        "api_key_injection_allowed_tiers",
        "api_key_service_allowlist",
        "api_key_service_blocklist",
        mode="before",
    )
    @classmethod
    def _parse_list_or_csv(cls, v: object) -> object:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return v
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return v

    def get_admin_emails(self) -> list[str]:
        return [
            email.strip().lower()
            for email in self.admin_emails.split(",")
            if email.strip()
        ]

    # Redis / RQ job queue
    redis_url: str = "redis://localhost:6379/0"
    transform_timeout: int = 300  # seconds per transform job
    rq_queue_name: str = "transforms"
    auto_run_migrations: bool = True

    # Cloud sandbox
    sandbox_enabled: bool = False  # auto-enabled in cloud mode
    sandbox_timeout: int = 30
    sandbox_memory_mb: int = 256
    sandbox_allowed_tiers: list[str] = ["official", "verified"]

    # Plugin API key policy
    api_key_injection_allow_community_plugins: bool = True
    api_key_injection_trusted_tiers_only: bool = False
    api_key_injection_allowed_tiers: list[str] = ["official", "verified"]
    api_key_service_allowlist: list[str] = []
    api_key_service_blocklist: list[str] = []

    @property
    def abs_database_path(self) -> Path:
        return Path(self.database_path).resolve()


settings = Settings()
