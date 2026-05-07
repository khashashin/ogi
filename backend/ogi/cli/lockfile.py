"""Lock file management for installed transforms.

The lock file (``plugins/ogi-lock.json``) tracks which transforms were
installed from the registry, their versions, and integrity hashes.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

LOCK_FILENAME = "ogi-lock.json"


class LockEntry(TypedDict, total=False):
    version: str
    category: str
    verification_tier: str
    installed_at: str
    sha256: str
    source: str
    python_dependencies: list[str]
    files: list[str]


class LockFile(TypedDict, total=False):
    lock_version: int
    ogi_version: str
    generated_at: str
    registry_repo: str
    transforms: dict[str, LockEntry]


def _default_lock(registry_repo: str, ogi_version: str) -> LockFile:
    return LockFile(
        lock_version=1,
        ogi_version=ogi_version,
        generated_at=datetime.now(timezone.utc).isoformat(),
        registry_repo=registry_repo,
        transforms={},
    )


def _apply_lock_defaults(lock: LockFile, registry_repo: str, ogi_version: str) -> LockFile:
    if "lock_version" not in lock:
        lock["lock_version"] = 1
    if "generated_at" not in lock:
        lock["generated_at"] = datetime.now(timezone.utc).isoformat()
    if not lock.get("registry_repo") and registry_repo:
        lock["registry_repo"] = registry_repo
    if not lock.get("ogi_version") and ogi_version:
        lock["ogi_version"] = ogi_version
    if "transforms" not in lock:
        lock["transforms"] = {}
    return lock


def read_lockfile(
    plugins_dir: Path,
    *,
    registry_repo: str = "",
    ogi_version: str = "",
) -> LockFile:
    """Read the lock file from *plugins_dir*, returning an empty lock if missing."""
    lock_path = plugins_dir / LOCK_FILENAME
    if not lock_path.exists():
        return _default_lock(registry_repo, ogi_version)
    try:
        with open(lock_path) as f:
            data: LockFile = json.load(f)
        return _apply_lock_defaults(data, registry_repo, ogi_version)
    except Exception as exc:
        logger.warning("Failed to read lock file %s: %s", lock_path, exc)
        return _default_lock(registry_repo, ogi_version)


def write_lockfile(plugins_dir: Path, lock: LockFile) -> None:
    """Persist *lock* to disk."""
    lock_path = plugins_dir / LOCK_FILENAME
    plugins_dir.mkdir(parents=True, exist_ok=True)
    lock["generated_at"] = datetime.now(timezone.utc).isoformat()
    with open(lock_path, "w") as f:
        json.dump(lock, f, indent=2)
    logger.info("Updated lock file %s", lock_path)


def add_entry(
    lock: LockFile,
    slug: str,
    *,
    version: str,
    category: str,
    verification_tier: str,
    sha256: str,
    source: str = "registry",
    python_dependencies: list[str] | None = None,
    files: list[str] | None = None,
) -> None:
    """Add or update an entry in *lock*."""
    transforms = lock.setdefault("transforms", {})
    transforms[slug] = LockEntry(
        version=version,
        category=category,
        verification_tier=verification_tier,
        installed_at=datetime.now(timezone.utc).isoformat(),
        sha256=sha256,
        source=source,
        python_dependencies=python_dependencies or [],
        files=files or [],
    )


def remove_entry(lock: LockFile, slug: str) -> bool:
    """Remove an entry from *lock*. Returns True if it existed."""
    transforms = lock.get("transforms", {})
    if slug in transforms:
        del transforms[slug]
        return True
    return False


def get_entry(lock: LockFile, slug: str) -> LockEntry | None:
    """Return a single lock entry or None."""
    return lock.get("transforms", {}).get(slug)
