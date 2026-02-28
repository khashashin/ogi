import os
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "OGI"
    database_path: str = os.environ.get("OGI_DB_PATH", "ogi.db")
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.database_path}"

    @property
    def abs_database_path(self) -> Path:
        return Path(self.database_path).resolve()


settings = Settings()
