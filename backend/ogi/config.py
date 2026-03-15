import os
from pathlib import Path
from typing import Any
from typing_extensions import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    transform_setting_max_overrides: Annotated[dict[str, float | None], NoDecode] = {}
    # Optional GitHub token for higher GitHub API limits and private registry access.
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

    @field_validator("transform_setting_max_overrides", mode="before")
    @classmethod
    def _parse_transform_setting_max_overrides(cls, v: object) -> dict[str, float | None]:
        if v in (None, "", {}):
            return {}
        if isinstance(v, dict):
            return {
                str(key).strip(): cls._parse_transform_cap_value(value)
                for key, value in v.items()
                if str(key).strip()
            }
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return {}
            if stripped.startswith("{"):
                import json

                parsed = json.loads(stripped)
                if not isinstance(parsed, dict):
                    raise ValueError("transform_setting_max_overrides JSON must be an object")
                return {
                    str(key).strip(): cls._parse_transform_cap_value(value)
                    for key, value in parsed.items()
                    if str(key).strip()
                }

            result: dict[str, float | None] = {}
            for part in stripped.split(","):
                item = part.strip()
                if not item:
                    continue
                if "=" not in item:
                    raise ValueError(
                        "transform_setting_max_overrides must use key=value pairs"
                    )
                key, raw = item.split("=", 1)
                key = key.strip()
                if not key:
                    continue
                result[key] = cls._parse_transform_cap_value(raw.strip())
            return result

        raise ValueError("Unsupported transform_setting_max_overrides value")

    @staticmethod
    def _parse_transform_cap_value(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"", "none", "null", "off", "unlimited", "inf", "infinite"}:
                return None
            return float(normalized)
        return float(value)

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

    # AI Investigator / Agent
    agent_enabled: bool = False
    agent_default_max_steps: int = 50
    agent_max_max_steps: int = 200
    agent_default_max_transforms: int = 20
    agent_max_max_transforms: int = 100
    agent_default_max_runtime_sec: int = 600
    agent_max_max_runtime_sec: int = 3600
    llm_provider: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_retry_max_attempts: int = 3

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
