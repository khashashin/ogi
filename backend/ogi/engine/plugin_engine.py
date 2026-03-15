"""Directory-based plugin discovery and transform loading.

Plugins live in configurable directories (default: ``plugins/``).
Each plugin is a subdirectory containing a ``plugin.yaml`` manifest and a
``transforms/`` package whose modules define ``BaseTransform`` subclasses.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import sys
from pathlib import Path

import yaml

from ogi.models import PluginInfo
from ogi.transforms.base import BaseTransform

logger = logging.getLogger(__name__)


class PluginEngine:
    def __init__(self, plugin_dirs: list[str]) -> None:
        self.plugin_dirs = plugin_dirs
        self.plugins: dict[str, PluginInfo] = {}
        self._plugin_transforms: dict[str, list[str]] = {}  # plugin_name -> transform_names

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> list[PluginInfo]:
        """Scan plugin directories for valid plugins with a ``plugin.yaml``."""
        discovered: list[PluginInfo] = []

        for dir_path_str in self.plugin_dirs:
            dir_path = Path(dir_path_str).resolve()
            if not dir_path.is_dir():
                continue

            for child in sorted(dir_path.iterdir()):
                if not child.is_dir():
                    continue
                manifest = child / "plugin.yaml"
                if not manifest.exists():
                    manifest = child / "plugin.yml"
                if not manifest.exists():
                    continue

                try:
                    with open(manifest) as f:
                        data = yaml.safe_load(f) or {}
                    info = self._parse_manifest(data, child.name)
                    discovered.append(info)
                except Exception as exc:
                    logger.warning("Failed to read plugin manifest %s: %s", manifest, exc)

        return discovered

    @staticmethod
    def _parse_manifest(data: dict[str, object], fallback_name: str) -> PluginInfo:
        """Parse a plugin.yaml manifest, supporting both v1 and v2 schemas."""
        schema_version = int(data.get("schema_version", 1))

        # v1 fields (always parsed)
        info = PluginInfo(
            name=str(data.get("name", fallback_name)),
            version=str(data.get("version", "")),
            display_name=str(data.get("display_name", data.get("name", fallback_name))),
            description=str(data.get("description", "")),
            author=str(data.get("author", "")),
            enabled=bool(data.get("enabled", True)),
            schema_version=schema_version,
        )

        # v2 additions
        if schema_version >= 2:
            info.category = str(data.get("category", ""))
            info.license = str(data.get("license", ""))
            info.author_github = str(data.get("author_github", ""))
            info.homepage = str(data.get("homepage", ""))
            info.repository = str(data.get("repository", ""))
            info.min_ogi_version = str(data.get("min_ogi_version", ""))
            info.icon = str(data.get("icon", ""))
            info.color = str(data.get("color", ""))

            raw_tags = data.get("tags")
            if isinstance(raw_tags, list):
                info.tags = [str(t) for t in raw_tags]

            raw_input = data.get("input_types")
            if isinstance(raw_input, list):
                info.input_types = [str(t) for t in raw_input]

            raw_output = data.get("output_types")
            if isinstance(raw_output, list):
                info.output_types = [str(t) for t in raw_output]

            raw_deps = data.get("python_dependencies")
            if isinstance(raw_deps, list):
                info.python_dependencies = [str(d) for d in raw_deps]

            raw_api_keys = data.get("api_keys_required")
            if isinstance(raw_api_keys, list):
                info.api_keys_required = [
                    {str(k): str(v) for k, v in entry.items()}
                    for entry in raw_api_keys
                    if isinstance(entry, dict)
                ]

            raw_perms = data.get("permissions")
            if isinstance(raw_perms, dict):
                info.permissions = {str(k): bool(v) for k, v in raw_perms.items()}

        return info

    # ------------------------------------------------------------------
    # Transform loading
    # ------------------------------------------------------------------

    def load_transforms(self, plugin_name: str) -> list[BaseTransform]:
        """Import and instantiate all BaseTransform subclasses from a plugin."""
        transforms: list[BaseTransform] = []

        for dir_path_str in self.plugin_dirs:
            plugin_dir = Path(dir_path_str).resolve() / plugin_name / "transforms"
            if not plugin_dir.is_dir():
                continue

            # Ensure the transforms package is importable
            if str(plugin_dir.parent) not in sys.path:
                sys.path.insert(0, str(plugin_dir.parent))

            for py_file in sorted(plugin_dir.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue

                module_name = f"plugin_{plugin_name}_{py_file.stem}"
                try:
                    spec = importlib.util.spec_from_file_location(module_name, str(py_file))
                    if spec is None or spec.loader is None:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)

                    for _name, obj in inspect.getmembers(module, inspect.isclass):
                        if (
                            issubclass(obj, BaseTransform)
                            and obj is not BaseTransform
                            and hasattr(obj, "name")
                            and obj.name
                        ):
                            transforms.append(obj())
                except Exception as exc:
                    logger.warning("Failed to load transforms from %s: %s", py_file, exc)

        return transforms

    # ------------------------------------------------------------------
    # Bulk loading
    # ------------------------------------------------------------------

    def load_all(self, transform_engine: object) -> None:
        """Discover all plugins and register their transforms.

        ``transform_engine`` is expected to have a ``register(transform)`` method.
        """
        from ogi.engine.transform_engine import TransformEngine
        assert isinstance(transform_engine, TransformEngine)

        for plugin_info in self.discover():
            if not plugin_info.enabled:
                logger.info("Skipping disabled plugin %s", plugin_info.name)
                continue

            transforms = self.load_transforms(plugin_info.name)
            names: list[str] = []
            for t in transforms:
                transform_engine.register(t)
                names.append(t.name)
                logger.info("Registered plugin transform: %s (from %s)", t.name, plugin_info.name)

            plugin_info.transform_count = len(transforms)
            plugin_info.transform_names = names
            self.plugins[plugin_info.name] = plugin_info
            self._plugin_transforms[plugin_info.name] = names

    def get_plugin(self, name: str) -> PluginInfo | None:
        return self.plugins.get(name)

    def list_plugins(self) -> list[PluginInfo]:
        return list(self.plugins.values())
