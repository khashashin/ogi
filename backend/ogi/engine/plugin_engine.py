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
from pydantic import BaseModel
from pydantic import Field as PydanticField

from ogi.models import PluginInfo
from ogi.transforms.base import BaseTransform

logger = logging.getLogger(__name__)

# READMEs are author-controlled and shipped verbatim by the installer; cap the
# amount we hand to the UI so one oversized file cannot bloat a response.
MAX_README_CHARS = 20000


class PluginDocumentation(BaseModel):
    """Long-form documentation declared in a plugin manifest."""

    long_description: str = ""
    when_to_use: str = ""
    limitations: str = ""
    example_use_cases: list[str] = PydanticField(default_factory=list)


class PluginEngine:
    def __init__(self, plugin_dirs: list[str]) -> None:
        self.plugin_dirs = plugin_dirs
        self.plugins: dict[str, PluginInfo] = {}
        self._plugin_transforms: dict[str, list[str]] = {}  # plugin_name -> transform_names
        self._plugin_docs: dict[str, PluginDocumentation] = {}

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
                    with open(manifest, encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                    info = self._parse_manifest(data, child.name)
                    discovered.append(info)
                    self._plugin_docs[info.name] = self._parse_documentation(data)
                except Exception as exc:
                    logger.warning("Failed to read plugin manifest %s: %s", manifest, exc)

        return discovered

    @staticmethod
    def _parse_documentation(data: dict[str, object]) -> PluginDocumentation:
        """Extract the optional long-form documentation fields from a manifest."""
        docs = PluginDocumentation(
            long_description=str(data.get("long_description", "") or ""),
            when_to_use=str(data.get("when_to_use", "") or ""),
            limitations=str(data.get("limitations", "") or ""),
        )
        raw_cases = data.get("example_use_cases")
        if isinstance(raw_cases, list):
            docs.example_use_cases = [str(case) for case in raw_cases if str(case).strip()]
        return docs

    @staticmethod
    def _parse_manifest(data: dict[str, object], fallback_name: str) -> PluginInfo:
        """Parse a plugin.yaml manifest using the current schema."""
        info = PluginInfo(
            name=str(data.get("name", fallback_name)),
            version=str(data.get("version", "")),
            display_name=str(data.get("display_name", data.get("name", fallback_name))),
            description=str(data.get("description", "")),
            author=str(data.get("author", "")),
            enabled=bool(data.get("enabled", True)),
        )

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
        if not isinstance(transform_engine, TransformEngine):
            raise TypeError("transform_engine must be a TransformEngine instance")

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

    def get_plugin_documentation(self, name: str) -> PluginDocumentation | None:
        return self._plugin_docs.get(name)

    def get_plugin_readme(self, name: str) -> str:
        """Return the plugin's README text, truncated, or '' when absent.

        The registry installer ships each transform's README alongside its
        manifest, so this is the richest documentation available for most
        community transforms.
        """
        if not name or "/" in name or "\\" in name or ".." in name:
            return ""

        for dir_path_str in self.plugin_dirs:
            plugin_dir = Path(dir_path_str).resolve() / name
            if not plugin_dir.is_dir():
                continue
            for candidate in ("README.md", "readme.md", "README.MD"):
                readme = plugin_dir / candidate
                if not readme.is_file():
                    continue
                try:
                    text = readme.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    logger.warning("Failed to read plugin README %s: %s", readme, exc)
                    return ""
                if len(text) > MAX_README_CHARS:
                    return text[:MAX_README_CHARS] + "\n\n_(truncated)_"
                return text
        return ""

    def get_plugin_for_transform(self, transform_name: str) -> str | None:
        for plugin_name, transform_names in self._plugin_transforms.items():
            if transform_name in transform_names:
                return plugin_name
        return None

    def list_plugins(self) -> list[PluginInfo]:
        return list(self.plugins.values())
