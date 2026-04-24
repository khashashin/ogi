from __future__ import annotations

from pathlib import Path

from ogi.cli.installer import TransformInstaller
from ogi.cli.lockfile import LockFile


class _DummyRegistry:
    def get_transform(self, slug: str):  # pragma: no cover - helper stub
        return None


def _installer(tmp_path: Path) -> TransformInstaller:
    return TransformInstaller(
        registry=_DummyRegistry(),  # type: ignore[arg-type]
        plugins_dir=tmp_path,
        ogi_version="0.3.0",
    )


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
