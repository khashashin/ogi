"""Encrypted API key storage for per-user transform credentials.

In SQLite mode, keys are stored in a simple JSON file (``api_keys.json``)
alongside the database.  In PostgreSQL mode, they are stored in the
``api_keys`` table with the key value encrypted (base64-encoded here;
in production use a proper encryption library).
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from uuid import UUID

import aiosqlite

from ogi.config import settings


class ApiKeyStore:
    """CRUD for per-user API keys (service_name → encrypted_key)."""

    def __init__(self, db: object) -> None:
        self.db = db
        self._is_sqlite = isinstance(db, aiosqlite.Connection)
        # SQLite fallback: store keys in a JSON file
        self._json_path = Path(settings.database_path).parent / "api_keys.json"
        if self._is_sqlite and settings.database_path == ":memory:":
            self._json_store: dict[str, dict[str, str]] = {}  # user_id -> {service: key}
        else:
            self._json_store = self._load_json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def list_services(self, user_id: UUID) -> list[str]:
        """Return service names for which the user has stored keys."""
        if self._is_sqlite:
            return list(self._json_store.get(str(user_id), {}).keys())
        pool = self.db
        rows = await pool.fetch(  # type: ignore[union-attr]
            "SELECT service_name FROM api_keys WHERE user_id = $1 ORDER BY service_name",
            user_id,
        )
        return [r["service_name"] for r in rows]

    async def get_key(self, user_id: UUID, service_name: str) -> str | None:
        """Return decrypted key or None."""
        if self._is_sqlite:
            return self._json_store.get(str(user_id), {}).get(service_name)
        pool = self.db
        row = await pool.fetchrow(  # type: ignore[union-attr]
            "SELECT encrypted_key FROM api_keys WHERE user_id = $1 AND service_name = $2",
            user_id, service_name,
        )
        if not row:
            return None
        return self._decrypt(row["encrypted_key"])

    async def set_key(self, user_id: UUID, service_name: str, key: str) -> None:
        """Store or update an API key."""
        if self._is_sqlite:
            uid = str(user_id)
            if uid not in self._json_store:
                self._json_store[uid] = {}
            self._json_store[uid][service_name] = key
            self._save_json()
            return

        pool = self.db
        encrypted = self._encrypt(key)
        await pool.execute(  # type: ignore[union-attr]
            """INSERT INTO api_keys (user_id, service_name, encrypted_key)
               VALUES ($1, $2, $3)
               ON CONFLICT (user_id, service_name) DO UPDATE SET encrypted_key = EXCLUDED.encrypted_key""",
            user_id, service_name, encrypted,
        )

    async def delete_key(self, user_id: UUID, service_name: str) -> bool:
        """Remove an API key. Returns True if one was deleted."""
        if self._is_sqlite:
            uid = str(user_id)
            if uid in self._json_store and service_name in self._json_store[uid]:
                del self._json_store[uid][service_name]
                self._save_json()
                return True
            return False

        pool = self.db
        result = await pool.execute(  # type: ignore[union-attr]
            "DELETE FROM api_keys WHERE user_id = $1 AND service_name = $2",
            user_id, service_name,
        )
        return result == "DELETE 1"

    # ------------------------------------------------------------------
    # Encryption helpers (simple base64 encoding — swap for Fernet/etc.)
    # ------------------------------------------------------------------

    @staticmethod
    def _encrypt(plain: str) -> str:
        return base64.b64encode(plain.encode()).decode()

    @staticmethod
    def _decrypt(encrypted: str) -> str:
        return base64.b64decode(encrypted.encode()).decode()

    # ------------------------------------------------------------------
    # JSON file helpers (SQLite fallback)
    # ------------------------------------------------------------------

    def _load_json(self) -> dict[str, dict[str, str]]:
        if self._json_path.exists():
            try:
                return json.loads(self._json_path.read_text())
            except Exception:
                pass
        return {}

    def _save_json(self) -> None:
        if settings.database_path == ":memory:":
            return
        self._json_path.write_text(json.dumps(self._json_store, indent=2))
