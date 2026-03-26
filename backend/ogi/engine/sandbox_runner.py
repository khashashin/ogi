"""Sandboxed transform execution for cloud mode.

Runs transforms inside ephemeral Docker containers with strict
resource limits and network restrictions.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

SANDBOX_IMAGE = "python:3.14-slim"
RUNNER_SCRIPT = """\
import json, sys, importlib, importlib.util, inspect, os

# Read input from stdin
data = json.loads(sys.stdin.read())
entity_data = data["entity"]
config_data = data.get("config", {"settings": {}})
transform_name = data["transform_name"]

# Add transform path to sys.path
sys.path.insert(0, "/transform")

# Find and load the transform
from pathlib import Path
transforms_dir = Path("/transform/transforms")
for py_file in sorted(transforms_dir.glob("*.py")):
    if py_file.name.startswith("_"):
        continue
    spec = importlib.util.spec_from_file_location(py_file.stem, str(py_file))
    if spec is None or spec.loader is None:
        continue
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for name, obj in inspect.getmembers(module, inspect.isclass):
        if hasattr(obj, "name") and obj.name == transform_name:
            instance = obj()
            import asyncio

            class _Entity:
                def __init__(self, d):
                    self.__dict__.update(d)

            class _Config:
                def __init__(self, d):
                    self.settings = d.get("settings", {})

            result = asyncio.run(instance.run(_Entity(entity_data), _Config(config_data)))
            output = {
                "entities": [e.dict() if hasattr(e, "dict") else e for e in (result.entities or [])],
                "edges": [e.dict() if hasattr(e, "dict") else e for e in (result.edges or [])],
                "messages": result.messages or [],
                "ui_messages": result.ui_messages or [],
            }
            print(json.dumps(output))
            sys.exit(0)

print(json.dumps({"error": f"Transform '{transform_name}' not found"}), file=sys.stderr)
sys.exit(1)
"""


class SandboxResult(TypedDict):
    entities: list[dict[str, object]]
    edges: list[dict[str, object]]
    messages: list[str]
    ui_messages: list[str]


class TransformPermissions(TypedDict, total=False):
    network: bool
    filesystem: bool
    subprocess: bool


class SandboxRunner:
    """Executes transforms in isolated Docker containers (cloud mode)."""

    def __init__(
        self,
        timeout: float = 30.0,
        memory_mb: int = 256,
    ) -> None:
        self.timeout = timeout
        self.memory_mb = memory_mb
        self._docker_available: bool | None = None

    def is_available(self) -> bool:
        """Check if Docker is installed and accessible."""
        if self._docker_available is not None:
            return self._docker_available
        docker = shutil.which("docker")
        if docker is None:
            self._docker_available = False
            return False
        try:
            result = subprocess.run(
                ["docker", "info"], capture_output=True, timeout=10
            )
            self._docker_available = result.returncode == 0
        except Exception:
            self._docker_available = False
        return self._docker_available

    async def run_sandboxed(
        self,
        transform_path: Path,
        entity: dict[str, object],
        transform_name: str,
        config: dict[str, object] | None = None,
        api_keys: dict[str, str] | None = None,
        permissions: TransformPermissions | None = None,
        timeout: float | None = None,
    ) -> SandboxResult:
        """Execute a transform in a Docker sandbox.

        Parameters
        ----------
        transform_path:
            Path to the transform directory (containing ``transforms/``).
        entity:
            Serialized entity dict.
        transform_name:
            The ``name`` attribute of the transform class to run.
        config:
            Transform config dict.
        api_keys:
            API keys to inject as environment variables.
        permissions:
            Declared permissions for network, filesystem, subprocess.
        timeout:
            Override the default timeout.
        """
        if not self.is_available():
            raise RuntimeError("Docker is not available for sandboxed execution")

        effective_timeout = timeout or self.timeout
        perms = permissions or TransformPermissions(
            network=False, filesystem=False, subprocess=False
        )

        # Prepare input payload
        payload = json.dumps({
            "entity": entity,
            "config": config or {"settings": {}},
            "transform_name": transform_name,
        })

        # Write runner script to temp directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner_path = Path(tmp_dir) / "runner.py"
            runner_path.write_text(RUNNER_SCRIPT)

            # Build docker run command
            cmd: list[str] = [
                "docker", "run",
                "--rm",
                f"--memory={self.memory_mb}m",
                "--cpus=1",
                "--read-only",
                "--tmpfs=/tmp:size=32m",
                f"-v={transform_path.resolve()}:/transform:ro",
                f"-v={runner_path.resolve()}:/runner.py:ro",
            ]

            # Network restrictions
            if not perms.get("network", False):
                cmd.append("--network=none")

            # Inject API keys
            if api_keys:
                for key, value in api_keys.items():
                    cmd.extend(["-e", f"{key}={value}"])

            cmd.extend([SANDBOX_IMAGE, "python", "/runner.py"])

            logger.info(
                "Running sandboxed transform %s (timeout=%.0fs, memory=%dMB)",
                transform_name, effective_timeout, self.memory_mb,
            )

            import asyncio
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=payload.encode()),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                raise TimeoutError(
                    f"Transform '{transform_name}' exceeded {effective_timeout}s timeout"
                )

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise RuntimeError(f"Sandboxed transform failed: {error_msg}")

            result: SandboxResult = json.loads(stdout.decode())
            return result
