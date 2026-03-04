"""User-level CLI config persisted at ~/.ogi/config.toml."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
import tomllib


ConfigDict = dict[str, Any]


DEFAULT_CONFIG: ConfigDict = {
    "registry": {
        "repo": "opengraphintel/ogi-transforms",
        "cache_ttl_hours": 1,
    },
    "plugins": {
        "dirs": ["plugins"],
    },
    "cli": {
        "auto_confirm": False,
        "api_base_url": "http://localhost:8000/api/v1",
    },
}

KNOWN_KEYS: tuple[str, ...] = (
    "registry.repo",
    "registry.cache_ttl_hours",
    "plugins.dirs",
    "cli.auto_confirm",
    "cli.api_base_url",
)


def get_config_path() -> Path:
    return Path.home() / ".ogi" / "config.toml"


def _deep_merge(base: ConfigDict, override: ConfigDict) -> ConfigDict:
    out = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)  # type: ignore[index]
        else:
            out[key] = value
    return out


def load_config() -> ConfigDict:
    path = get_config_path()
    if not path.exists():
        return deepcopy(DEFAULT_CONFIG)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return deepcopy(DEFAULT_CONFIG)
        return _deep_merge(DEFAULT_CONFIG, raw)
    except Exception:
        return deepcopy(DEFAULT_CONFIG)


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return f"\"{str(value).replace('\"', '\\\"')}\""


def _format_array(values: list[Any]) -> str:
    return "[{}]".format(", ".join(_format_scalar(v) for v in values))


def _to_toml_text(cfg: ConfigDict) -> str:
    lines: list[str] = []
    for section in ("registry", "plugins", "cli"):
        data = cfg.get(section, {})
        if not isinstance(data, dict):
            continue
        lines.append(f"[{section}]")
        for key, value in data.items():
            if isinstance(value, list):
                lines.append(f"{key} = {_format_array(value)}")
            else:
                lines.append(f"{key} = {_format_scalar(value)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def save_config(cfg: ConfigDict) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_toml_text(cfg), encoding="utf-8")


def ensure_config_file() -> ConfigDict:
    cfg = load_config()
    path = get_config_path()
    if not path.exists():
        save_config(cfg)
    return cfg


def get_value(cfg: ConfigDict, dotted_key: str) -> Any:
    if dotted_key not in KNOWN_KEYS:
        raise KeyError(f"Unknown config key '{dotted_key}'")
    section, key = dotted_key.split(".", 1)
    section_obj = cfg.get(section, {})
    if not isinstance(section_obj, dict):
        raise KeyError(f"Unknown config section '{section}'")
    return section_obj.get(key)


def _parse_value(dotted_key: str, raw_value: str) -> Any:
    raw_value = raw_value.strip()
    if dotted_key == "registry.cache_ttl_hours":
        parsed = int(raw_value)
        if parsed <= 0:
            raise ValueError("registry.cache_ttl_hours must be > 0")
        return parsed
    if dotted_key == "cli.auto_confirm":
        low = raw_value.lower()
        if low in {"true", "1", "yes", "on"}:
            return True
        if low in {"false", "0", "no", "off"}:
            return False
        raise ValueError("cli.auto_confirm must be a boolean")
    if dotted_key == "plugins.dirs":
        return [part.strip() for part in raw_value.split(",") if part.strip()]
    return raw_value


def set_value(cfg: ConfigDict, dotted_key: str, raw_value: str) -> ConfigDict:
    if dotted_key not in KNOWN_KEYS:
        raise KeyError(f"Unknown config key '{dotted_key}'")
    section, key = dotted_key.split(".", 1)
    value = _parse_value(dotted_key, raw_value)
    out = deepcopy(cfg)
    out.setdefault(section, {})
    section_obj = out[section]
    if not isinstance(section_obj, dict):
        section_obj = {}
        out[section] = section_obj
    section_obj[key] = value
    return out


def reset_value(cfg: ConfigDict, dotted_key: str | None = None) -> ConfigDict:
    if dotted_key is None:
        return deepcopy(DEFAULT_CONFIG)
    if dotted_key not in KNOWN_KEYS:
        raise KeyError(f"Unknown config key '{dotted_key}'")
    section, key = dotted_key.split(".", 1)
    out = deepcopy(cfg)
    default_section = DEFAULT_CONFIG.get(section, {})
    if not isinstance(default_section, dict):
        raise KeyError(f"Unknown config section '{section}'")
    out.setdefault(section, {})
    section_obj = out[section]
    if not isinstance(section_obj, dict):
        section_obj = {}
        out[section] = section_obj
    section_obj[key] = default_section.get(key)
    return out
