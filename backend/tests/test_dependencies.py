import pytest

from ogi.api import dependencies
from ogi.cli.installer import TransformInstaller
from ogi.cli.registry import RegistryClient
from ogi.engine.entity_registry import EntityRegistry
from ogi.engine.plugin_engine import PluginEngine
from ogi.engine.transform_engine import TransformEngine


@pytest.fixture(autouse=True)
def reset_singletons(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dependencies, "_transform_engine", None)
    monkeypatch.setattr(dependencies, "_entity_registry", None)
    monkeypatch.setattr(dependencies, "_plugin_engine", None)
    monkeypatch.setattr(dependencies, "_registry_client", None)
    monkeypatch.setattr(dependencies, "_transform_installer", None)


@pytest.mark.parametrize(
    ("getter", "name"),
    [
        (dependencies.get_transform_engine, "Transform engine"),
        (dependencies.get_entity_registry, "Entity registry"),
        (dependencies.get_plugin_engine, "Plugin engine"),
        (dependencies.get_registry_client, "Registry client"),
        (dependencies.get_transform_installer, "Transform installer"),
    ],
)
def test_singleton_getters_raise_when_uninitialized(getter, name: str):
    with pytest.raises(RuntimeError, match=f"{name} has not been initialized"):
        getter()


def test_singleton_getters_return_initialized_instances():
    transform_engine = TransformEngine()
    entity_registry = EntityRegistry.instance()
    plugin_engine = PluginEngine(["plugins"])
    registry_client = RegistryClient(repo="example/repo")
    installer = TransformInstaller(registry_client, plugins_dir=plugin_engine_path())

    dependencies.init_transform_engine(transform_engine)
    dependencies.init_entity_registry(entity_registry)
    dependencies.init_plugin_engine(plugin_engine)
    dependencies.init_registry_client(registry_client)
    dependencies.init_transform_installer(installer)

    assert dependencies.get_transform_engine() is transform_engine
    assert dependencies.get_entity_registry() is entity_registry
    assert dependencies.get_plugin_engine() is plugin_engine
    assert dependencies.get_registry_client() is registry_client
    assert dependencies.get_transform_installer() is installer


def plugin_engine_path():
    from pathlib import Path

    return Path("plugins")
