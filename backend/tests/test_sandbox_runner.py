from pathlib import Path

import pytest

from ogi.engine.plugin_engine import PluginEngine
from ogi.engine.sandbox_runner import SandboxRunner
from ogi.engine.transform_engine import TransformEngine


def test_plugin_engine_load_all_requires_transform_engine():
    engine = PluginEngine(["plugins"])

    with pytest.raises(TypeError, match="TransformEngine"):
        engine.load_all(object())


def test_sandbox_runner_uses_resolved_docker_path(monkeypatch: pytest.MonkeyPatch):
    runner = SandboxRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr("ogi.engine.sandbox_runner.shutil.which", lambda _: "/usr/bin/docker")

    class Result:
        returncode = 0

    def fake_run(cmd: list[str], capture_output: bool, timeout: int):
        calls.append(cmd)
        return Result()

    monkeypatch.setattr("ogi.engine.sandbox_runner.subprocess.run", fake_run)

    assert runner.is_available() is True
    assert calls == [["/usr/bin/docker", "info"]]


@pytest.mark.asyncio
async def test_sandbox_runner_run_sandboxed_uses_resolved_docker_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    runner = SandboxRunner()
    runner._docker_available = True
    runner._docker_path = "/usr/bin/docker"
    recorded: list[str] = []

    class FakeProcess:
        returncode = 0

        async def communicate(self, input: bytes):
            return (b'{"entities":[],"edges":[],"messages":[],"ui_messages":[]}', b"")

    async def fake_create_subprocess_exec(*cmd, **kwargs):
        recorded.extend(cmd)
        return FakeProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = await runner.run_sandboxed(
        transform_path=tmp_path,
        entity={},
        transform_name="demo",
    )

    assert recorded[0] == "/usr/bin/docker"
    assert result["entities"] == []
