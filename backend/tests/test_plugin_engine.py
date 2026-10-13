from pathlib import Path

from ogi.engine.plugin_engine import PluginEngine
from ogi.engine.transform_engine import TransformEngine

TRANSFORM_SOURCE = '''
from ogi.models import Entity, EntityType, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


class DemoTransform(BaseTransform):
    name = "{name}"
    display_name = "Demo"
    input_types = [EntityType.DOMAIN]
    output_types = [EntityType.DOMAIN]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        return TransformResult()
'''


def _write_plugin(root: Path, version: str, transform_name: str) -> None:
    plugin_dir = root / "demo-plugin"
    (plugin_dir / "transforms").mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.yaml").write_text(
        f'name: demo-plugin\nversion: "{version}"\ndescription: "Demo {version}"\n',
        encoding="utf-8",
    )
    (plugin_dir / "transforms" / "__init__.py").write_text("", encoding="utf-8")
    (plugin_dir / "transforms" / "demo.py").write_text(
        TRANSFORM_SOURCE.format(name=transform_name), encoding="utf-8"
    )


def test_reload_plugin_refreshes_manifest_and_transforms(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "1.0.0", "demo_transform")
    plugin_engine = PluginEngine([str(tmp_path)])
    transform_engine = TransformEngine()
    plugin_engine.load_all(transform_engine)
    loaded = plugin_engine.get_plugin("demo-plugin")
    assert loaded is not None and loaded.version == "1.0.0"

    # Simulate an install or update replacing the files on disk.
    _write_plugin(tmp_path, "1.1.0", "demo_transform_v2")
    plugin = plugin_engine.reload_plugin("demo-plugin", transform_engine)

    assert plugin is not None
    assert plugin.version == "1.1.0"
    assert plugin.description == "Demo 1.1.0"
    assert plugin_engine.get_plugin("demo-plugin") is plugin
    assert plugin.transform_names == ["demo_transform_v2"]
    assert transform_engine.get_transform("demo_transform_v2") is not None
    assert transform_engine.get_transform("demo_transform") is None


def test_reload_plugin_returns_none_for_unknown_plugin(tmp_path: Path) -> None:
    plugin_engine = PluginEngine([str(tmp_path)])

    assert plugin_engine.reload_plugin("missing-plugin", TransformEngine()) is None
