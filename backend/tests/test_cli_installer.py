from __future__ import annotations

from pathlib import Path
import tomllib

import pytest

from ogi.cli.installer import InstallError, TransformInstaller, get_runtime_ogi_version
from ogi.cli.lockfile import LOCK_FILENAME, LockFile, read_lockfile, write_lockfile


class _DummyRegistry:
    repo = "opengraphintel/ogi-transforms"

    def get_transform(self, slug: str):  # pragma: no cover - helper stub
        return None


class _VersionRegistry:
    repo = "opengraphintel/ogi-transforms"

    def __init__(self, versions: dict[str, str]) -> None:
        self.versions = versions

    def get_transform(self, slug: str) -> dict[str, str] | None:
        version = self.versions.get(slug)
        return {"slug": slug, "version": version} if version else None


def _installer(tmp_path: Path) -> TransformInstaller:
    return TransformInstaller(
        registry=_DummyRegistry(),  # type: ignore[arg-type]
        plugins_dir=tmp_path,
        ogi_version="0.3.0",
    )


def _versioned_installer(tmp_path: Path, versions: dict[str, str]) -> TransformInstaller:
    return TransformInstaller(
        registry=_VersionRegistry(versions),  # type: ignore[arg-type]
        plugins_dir=tmp_path,
        ogi_version="0.3.0",
    )


def _write_manifest(plugins_dir: Path, dir_name: str, name: str, version: str) -> None:
    plugin_dir = plugins_dir / dir_name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.yaml").write_text(
        f'name: {name}\nversion: "{version}"\n', encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_check_updates_includes_plugins_missing_from_lock(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "username-maigret", "username-maigret", "1.0.0")
    # A directory whose manifest names a different plugin is not that registry transform.
    _write_manifest(tmp_path, "domain-to-ip", "my-custom-plugin", "0.1.0")
    installer = _versioned_installer(
        tmp_path, {"username-maigret": "1.3.0", "domain-to-ip": "2.0.0"}
    )

    assert await installer.check_updates() == [("username-maigret", "1.0.0", "1.3.0")]


@pytest.mark.asyncio
async def test_check_updates_prefers_lock_version_over_manifest(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "username-maigret", "username-maigret", "1.0.0")
    installer = _versioned_installer(tmp_path, {"username-maigret": "1.3.0"})
    lock = installer._lock()
    lock["transforms"] = {"username-maigret": {"version": "1.2.0"}}
    write_lockfile(tmp_path, lock)

    assert await installer.check_updates() == [("username-maigret", "1.2.0", "1.3.0")]


@pytest.mark.asyncio
async def test_update_reinstalls_plugin_missing_from_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_manifest(tmp_path, "username-maigret", "username-maigret", "1.0.0")
    installer = _versioned_installer(tmp_path, {"username-maigret": "1.3.0"})
    installed: list[str] = []

    async def fake_install(slug: str) -> list[str]:
        installed.append(slug)
        return []

    monkeypatch.setattr(installer, "install", fake_install)

    assert await installer.update("username-maigret") is True
    assert installed == ["username-maigret"]


@pytest.mark.asyncio
async def test_update_rejects_transform_that_is_not_installed(tmp_path: Path) -> None:
    installer = _versioned_installer(tmp_path, {"username-maigret": "1.3.0"})

    with pytest.raises(InstallError, match="not installed"):
        await installer.update("username-maigret")


def test_sync_boot_requirements_writes_unique_sorted_dependencies(tmp_path: Path) -> None:
    installer = _installer(tmp_path)
    lock: LockFile = {
        "transforms": {
            "a": {"python_dependencies": ["b==1.0.0", "a>=2.0"]},
            "b": {"python_dependencies": ["a>=2.0", ""]},
            "c": {"python_dependencies": []},
        }
    }

    installer._sync_boot_requirements(lock)

    req = (tmp_path / "requirements.txt").read_text(encoding="utf-8")
    assert req == "a>=2.0\nb==1.0.0\n"


def test_sync_boot_requirements_removes_file_when_no_dependencies(tmp_path: Path) -> None:
    installer = _installer(tmp_path)
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("x==1.0.0\n", encoding="utf-8")

    installer._sync_boot_requirements({"transforms": {}})

    assert not req_file.exists()


def test_installer_lock_populates_registry_and_ogi_metadata(tmp_path: Path) -> None:
    installer = _installer(tmp_path)

    lock = installer._lock()

    assert lock["registry_repo"] == "opengraphintel/ogi-transforms"
    assert lock["ogi_version"] == "0.3.0"
    assert lock["transforms"] == {}


def test_read_lockfile_backfills_missing_top_level_metadata(tmp_path: Path) -> None:
    lock_path = tmp_path / LOCK_FILENAME
    lock_path.write_text(
        '{\n'
        '  "lock_version": 1,\n'
        '  "ogi_version": "",\n'
        '  "generated_at": "2026-03-09T00:00:00+00:00",\n'
        '  "registry_repo": "",\n'
        '  "transforms": {}\n'
        '}\n',
        encoding="utf-8",
    )

    lock = read_lockfile(
        tmp_path,
        registry_repo="opengraphintel/ogi-transforms",
        ogi_version="0.3.0",
    )

    assert lock["registry_repo"] == "opengraphintel/ogi-transforms"
    assert lock["ogi_version"] == "0.3.0"


def test_get_runtime_ogi_version_matches_project_version() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as fh:
        pyproject = tomllib.load(fh)

    assert get_runtime_ogi_version() == pyproject["project"]["version"]
