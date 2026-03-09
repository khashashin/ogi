"""Download, verify, and install transforms from the registry."""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

from ogi.cli.lockfile import (
    LockFile,
    add_entry,
    read_lockfile,
    remove_entry,
    write_lockfile,
)
from ogi.cli.registry import RegistryClient, RegistryTransform

logger = logging.getLogger(__name__)


class InstallError(Exception):
    """Raised when a transform cannot be installed."""


class TransformInstaller:
    """Handles downloading, verifying, and installing transforms."""

    def __init__(
        self,
        registry: RegistryClient,
        plugins_dir: Path,
        ogi_version: str = "0.3.0",
    ) -> None:
        self.registry = registry
        self.plugins_dir = plugins_dir
        self.ogi_version = ogi_version

    def _lock(self) -> LockFile:
        return read_lockfile(
            self.plugins_dir,
            registry_repo=self.registry.repo,
            ogi_version=self.ogi_version,
        )

    def _save_lock(self, lock: LockFile) -> None:
        write_lockfile(self.plugins_dir, lock)
        self._sync_boot_requirements(lock)

    async def install(self, slug: str) -> list[str]:
        """Install a transform from the registry.

        Returns the list of files that were installed.

        Raises :class:`InstallError` on failure.
        """
        meta = self.registry.get_transform(slug)
        if meta is None:
            raise InstallError(f"Transform '{slug}' not found in registry")

        if meta.get("bundled"):
            raise InstallError(f"Transform '{slug}' is bundled with OGI — no install needed")

        # Version compatibility check
        min_ver = meta.get("min_ogi_version", "")
        if min_ver and min_ver > self.ogi_version:
            raise InstallError(
                f"Transform '{slug}' requires OGI >= {min_ver} (you have {self.ogi_version})"
            )

        category = meta.get("category", "")
        target_dir = self.plugins_dir / slug

        if target_dir.exists():
            shutil.rmtree(target_dir)

        target_dir.mkdir(parents=True, exist_ok=True)

        files = await self.registry.download_transform(slug, category, target_dir)

        # Verify checksum
        expected_sha = meta.get("sha256", "")
        if expected_sha:
            actual_sha = RegistryClient.compute_sha256(target_dir)
            if actual_sha != expected_sha:
                shutil.rmtree(target_dir)
                raise InstallError(
                    f"Checksum mismatch for '{slug}': "
                    f"expected {expected_sha[:12]}..., got {actual_sha[:12]}..."
                )

        # Install Python dependencies
        deps = meta.get("python_dependencies", [])
        if deps:
            self._install_dependencies(deps)

        # Update lock file
        lock = self._lock()
        add_entry(
            lock,
            slug,
            version=meta.get("version", ""),
            category=category,
            verification_tier=meta.get("verification_tier", "community"),
            sha256=expected_sha or RegistryClient.compute_sha256(target_dir),
            python_dependencies=deps,
            files=files,
        )
        self._save_lock(lock)

        return files

    async def update(self, slug: str) -> bool:
        """Update a single installed transform to the latest version.

        Returns True if an update was applied.
        """
        lock = self._lock()
        entry = lock.get("transforms", {}).get(slug)
        if entry is None:
            raise InstallError(f"Transform '{slug}' is not installed")

        meta = self.registry.get_transform(slug)
        if meta is None:
            raise InstallError(f"Transform '{slug}' not found in registry")

        if meta.get("version", "") == entry.get("version", ""):
            return False

        await self.install(slug)
        return True

    async def check_updates(self) -> list[tuple[str, str, str]]:
        """Return list of (slug, installed_version, latest_version) for outdated transforms."""
        lock = self._lock()
        updates: list[tuple[str, str, str]] = []
        for slug, entry in lock.get("transforms", {}).items():
            meta = self.registry.get_transform(slug)
            if meta is None:
                continue
            latest = meta.get("version", "")
            installed = entry.get("version", "")
            if latest and installed and latest != installed:
                updates.append((slug, installed, latest))
        return updates

    def remove(self, slug: str) -> None:
        """Uninstall a transform."""
        lock = self._lock()
        entry = lock.get("transforms", {}).get(slug)
        if entry is None:
            raise InstallError(f"Transform '{slug}' is not installed from registry")

        target_dir = self.plugins_dir / slug
        if target_dir.exists():
            shutil.rmtree(target_dir)

        remove_entry(lock, slug)
        self._save_lock(lock)

    def list_installed(self) -> dict[str, dict[str, str]]:
        """Return slug -> lock entry for all installed transforms."""
        lock = self._lock()
        return dict(lock.get("transforms", {}))

    @staticmethod
    def _install_dependencies(deps: list[str]) -> None:
        """Install Python packages using uv (preferred) or pip."""
        uv = shutil.which("uv")
        if uv:
            cmd = [uv, "pip", "install"] + deps
        else:
            cmd = [sys.executable, "-m", "pip", "install"] + deps

        logger.info("Installing dependencies: %s", " ".join(deps))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning("Dependency install stderr: %s", result.stderr)
            raise InstallError(f"Failed to install dependencies: {result.stderr[:500]}")

    def _sync_boot_requirements(self, lock: LockFile) -> None:
        """Sync shared boot requirements file from installed transform dependencies.

        Containers install this file on startup via ``entrypoint.sh`` so backend and
        worker environments stay aligned after plugin installs.
        """
        deps: set[str] = set()
        for entry in lock.get("transforms", {}).values():
            raw = entry.get("python_dependencies", [])
            if not isinstance(raw, list):
                continue
            for dep in raw:
                dep_text = str(dep).strip()
                if dep_text:
                    deps.add(dep_text)

        req_file = self.plugins_dir / "requirements.txt"
        if not deps:
            req_file.unlink(missing_ok=True)
            return

        req_file.parent.mkdir(parents=True, exist_ok=True)
        req_file.write_text("".join(f"{dep}\n" for dep in sorted(deps)), encoding="utf-8")
