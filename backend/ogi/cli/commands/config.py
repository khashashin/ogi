"""`ogi config` sub-commands for CLI configuration."""
from __future__ import annotations

import json

import typer

from ogi.cli.user_config import (
    KNOWN_KEYS,
    ensure_config_file,
    get_config_path,
    get_value,
    reset_value,
    save_config,
    set_value,
)

app = typer.Typer(help="Manage OGI CLI config in ~/.ogi/config.toml.")


@app.command("show")
def show_config() -> None:
    """Print full CLI config."""
    cfg = ensure_config_file()
    typer.echo(json.dumps(cfg, indent=2))
    typer.echo(f"\nPath: {get_config_path()}")


@app.command("get")
def get_config_value(
    key: str = typer.Argument(..., help=f"Key to read. Known keys: {', '.join(KNOWN_KEYS)}"),
) -> None:
    """Get a single config value."""
    cfg = ensure_config_file()
    try:
        value = get_value(cfg, key)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(value))


@app.command("set")
def set_config_value(
    key: str = typer.Argument(..., help=f"Key to write. Known keys: {', '.join(KNOWN_KEYS)}"),
    value: str = typer.Argument(..., help="Value to set"),
) -> None:
    """Set a single config value."""
    cfg = ensure_config_file()
    try:
        updated = set_value(cfg, key, value)
    except (KeyError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    save_config(updated)
    typer.echo(f"Updated {key}.")
    typer.echo(f"Path: {get_config_path()}")


@app.command("reset")
def reset_config(
    key: str | None = typer.Argument(None, help=f"Optional key to reset. Known keys: {', '.join(KNOWN_KEYS)}"),
) -> None:
    """Reset full config or a single key to defaults."""
    cfg = ensure_config_file()
    try:
        updated = reset_value(cfg, key)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    save_config(updated)
    if key:
        typer.echo(f"Reset {key}.")
    else:
        typer.echo("Reset full config.")
    typer.echo(f"Path: {get_config_path()}")
