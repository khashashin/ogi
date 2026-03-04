from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ogi.cli.commands import config as config_commands
from ogi.cli.main import app
from ogi.cli import user_config


def _patch_config_path(monkeypatch, tmp_path: Path) -> Path:
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr(user_config, "get_config_path", lambda: config_path)
    monkeypatch.setattr(config_commands, "get_config_path", lambda: config_path)
    return config_path


def test_ensure_config_file_creates_defaults(monkeypatch, tmp_path: Path) -> None:
    config_path = _patch_config_path(monkeypatch, tmp_path)
    cfg = user_config.ensure_config_file()

    assert config_path.exists()
    assert cfg["registry"]["repo"] == "opengraphintel/ogi-transforms"
    assert cfg["registry"]["cache_ttl_hours"] == 1
    assert cfg["plugins"]["dirs"] == ["plugins"]


def test_config_set_get_reset_roundtrip(monkeypatch, tmp_path: Path) -> None:
    _patch_config_path(monkeypatch, tmp_path)
    cfg = user_config.ensure_config_file()

    cfg = user_config.set_value(cfg, "registry.repo", "example/repo")
    cfg = user_config.set_value(cfg, "registry.cache_ttl_hours", "4")
    cfg = user_config.set_value(cfg, "plugins.dirs", "plugins, custom_plugins")
    cfg = user_config.set_value(cfg, "cli.auto_confirm", "true")
    user_config.save_config(cfg)

    reloaded = user_config.load_config()
    assert user_config.get_value(reloaded, "registry.repo") == "example/repo"
    assert user_config.get_value(reloaded, "registry.cache_ttl_hours") == 4
    assert user_config.get_value(reloaded, "plugins.dirs") == ["plugins", "custom_plugins"]
    assert user_config.get_value(reloaded, "cli.auto_confirm") is True

    reset = user_config.reset_value(reloaded, "registry.repo")
    assert user_config.get_value(reset, "registry.repo") == "opengraphintel/ogi-transforms"


def test_config_set_invalid_ttl_raises(monkeypatch, tmp_path: Path) -> None:
    _patch_config_path(monkeypatch, tmp_path)
    cfg = user_config.ensure_config_file()

    try:
        user_config.set_value(cfg, "registry.cache_ttl_hours", "0")
    except ValueError as exc:
        assert "must be > 0" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_config_cli_commands(monkeypatch, tmp_path: Path) -> None:
    config_path = _patch_config_path(monkeypatch, tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["config", "set", "registry.repo", "acme/transforms"])
    assert result.exit_code == 0
    assert config_path.exists()

    result = runner.invoke(app, ["config", "get", "registry.repo"])
    assert result.exit_code == 0
    assert "acme/transforms" in result.stdout

    result = runner.invoke(app, ["config", "reset", "registry.repo"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "opengraphintel/ogi-transforms" in result.stdout
