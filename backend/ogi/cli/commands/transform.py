"""``ogi transform`` sub-commands for the CLI."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Any, Coroutine

import typer

from ogi.cli.backend_client import try_reload_plugin
from ogi.cli.registry import RegistryClient
from ogi.cli.installer import TransformInstaller, InstallError
from ogi.cli.user_config import ConfigDict, load_config

app = typer.Typer(help="Manage transforms from the OGI registry.")


def _cli_config() -> ConfigDict:
    return load_config()


def _get_registry(cfg: ConfigDict) -> RegistryClient:
    registry_cfg = cfg.get("registry", {})
    repo = "opengraphintel/ogi-transforms"
    cache_ttl_hours = 1
    if isinstance(registry_cfg, dict):
        raw_repo = registry_cfg.get("repo")
        if isinstance(raw_repo, str) and raw_repo.strip():
            repo = raw_repo.strip()
        raw_ttl = registry_cfg.get("cache_ttl_hours")
        if isinstance(raw_ttl, int) and raw_ttl > 0:
            cache_ttl_hours = raw_ttl
    return RegistryClient(repo=repo, cache_ttl=timedelta(hours=cache_ttl_hours))


def _plugins_dir(cfg: ConfigDict) -> Path:
    plugins_cfg = cfg.get("plugins", {})
    if isinstance(plugins_cfg, dict):
        dirs = plugins_cfg.get("dirs")
        if isinstance(dirs, list):
            for entry in dirs:
                if isinstance(entry, str) and entry.strip():
                    return Path(entry.strip()).resolve()
    return Path("plugins").resolve()


def _get_installer(registry: RegistryClient, cfg: ConfigDict) -> TransformInstaller:
    plugins_dir = _plugins_dir(cfg)
    plugins_dir.mkdir(parents=True, exist_ok=True)
    return TransformInstaller(registry, plugins_dir)


def _run(coro: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coro)


@app.command()
def search(
    query: str = typer.Argument("", help="Search query (name, tag, description)"),
    category: str | None = typer.Option(None, "--category", "-c", help="Filter by category"),
) -> None:
    """Search for transforms in the registry."""
    cfg = _cli_config()
    registry = _get_registry(cfg)
    _run(registry.fetch_index())

    results = registry.search(query, category=category)

    if not results:
        typer.echo("No transforms found.")
        raise typer.Exit()

    typer.echo(f"\n  {'NAME':<28} {'CATEGORY':<16} {'AUTHOR':<16} {'VERSION':<10} {'TIER'}")
    typer.echo(f"  {'─' * 28} {'─' * 16} {'─' * 16} {'─' * 10} {'─' * 12}")
    for t in results:
        typer.echo(
            f"  {t.get('slug', ''):<28} "
            f"{t.get('category', ''):<16} "
            f"{t.get('author', ''):<16} "
            f"{t.get('version', ''):<10} "
            f"{t.get('verification_tier', '')}"
        )

    typer.echo(f"\n  {len(results)} transform(s) found. Use `ogi transform install <name>` to install.\n")


@app.command()
def install(
    slug: str = typer.Argument(..., help="Transform slug to install"),
) -> None:
    """Install a transform from the registry."""
    cfg = _cli_config()
    registry = _get_registry(cfg)
    _run(registry.fetch_index())
    installer = _get_installer(registry, cfg)

    typer.echo(f"\n  Installing {slug}...")
    try:
        files = _run(installer.install(slug))
    except InstallError as exc:
        typer.echo(f"  Error: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(f"  Downloaded {len(files)} file(s).")

    meta = registry.get_transform(slug)
    if meta:
        deps = meta.get("python_dependencies", [])
        if deps:
            typer.echo(f"  Dependencies installed: {', '.join(deps)}")

        api_keys = meta.get("api_keys_required", [])
        if api_keys:
            typer.echo("")
            for key_info in api_keys:
                svc = key_info.get("service", "unknown")
                env_var = key_info.get("env_var", "")
                typer.echo(f"  Warning: Requires API key: {env_var} ({svc})")
            typer.echo("  Configure via: Settings > API Keys in the UI")

    typer.echo(f"  {slug} installed successfully.")

    reloaded, message = _run(try_reload_plugin(slug, cfg))
    if reloaded:
        typer.echo(f"  {message}\n")
    else:
        typer.echo(f"  Warning: {message}\n")


@app.command("list")
def list_transforms() -> None:
    """List installed and available transforms."""
    cfg = _cli_config()
    registry = _get_registry(cfg)
    _run(registry.fetch_index())
    installer = _get_installer(registry, cfg)

    installed = installer.list_installed()
    all_transforms = registry.search("")
    bundled = [t for t in all_transforms if t.get("bundled")]

    typer.echo("\n  INSTALLED:")
    if not installed:
        typer.echo("    (none)")
    for slug_key, entry in installed.items():
        typer.echo(
            f"    {slug_key:<28} "
            f"{entry.get('version', ''):<10} "
            f"{entry.get('category', ''):<12} "
            f"{entry.get('verification_tier', ''):<12} "
            f"{entry.get('source', 'registry')}"
        )

    typer.echo("\n  BUNDLED (built-in):")
    if not bundled:
        typer.echo("    (none)")
    for t in bundled[:20]:
        typer.echo(
            f"    {t.get('slug', ''):<28} "
            f"{t.get('version', ''):<10} "
            f"{t.get('category', ''):<12} "
            f"{t.get('verification_tier', ''):<12} "
            f"bundled"
        )
    if len(bundled) > 20:
        typer.echo(f"    ... and {len(bundled) - 20} more")

    available = [
        t for t in all_transforms
        if t.get("slug", "") not in installed and not t.get("bundled")
    ]
    typer.echo("\n  AVAILABLE (not installed):")
    if not available:
        typer.echo("    (none)")
    for t in available[:20]:
        typer.echo(
            f"    {t.get('slug', ''):<28} "
            f"{t.get('version', ''):<10} "
            f"{t.get('category', ''):<12} "
            f"{t.get('verification_tier', ''):<12} "
            f"registry"
        )
    if len(available) > 20:
        typer.echo(f"    ... and {len(available) - 20} more")

    typer.echo(f"\n  {len(installed)} installed, {len(bundled)} bundled, {len(available)} available.\n")


@app.command()
def update(
    slug: str | None = typer.Argument(None, help="Transform slug to update (all if omitted)"),
) -> None:
    """Update installed transforms to the latest version."""
    cfg = _cli_config()
    registry = _get_registry(cfg)
    _run(registry.fetch_index())
    installer = _get_installer(registry, cfg)

    if slug:
        try:
            updated = _run(installer.update(slug))
        except InstallError as exc:
            typer.echo(f"  Error: {exc}", err=True)
            raise typer.Exit(1)
        if updated:
            typer.echo(f"  {slug} updated successfully.")
            reloaded, message = _run(try_reload_plugin(slug, cfg))
            if reloaded:
                typer.echo(f"  {message}")
            else:
                typer.echo(f"  Warning: {message}")
        else:
            typer.echo(f"  {slug} is already up to date.")
    else:
        updates = _run(installer.check_updates())
        if not updates:
            typer.echo("  All transforms are up to date.")
            return
        for s, old, new in updates:  # type: ignore[misc]
            typer.echo(f"  Updating {s}: {old} -> {new}...")
            try:
                updated = _run(installer.update(s))
                if updated:
                    reloaded, message = _run(try_reload_plugin(s, cfg))
                    if reloaded:
                        typer.echo(f"    {message}")
                    else:
                        typer.echo(f"    Warning: {message}")
            except InstallError as exc:
                typer.echo(f"    Error updating {s}: {exc}", err=True)


@app.command()
def remove(
    slug: str = typer.Argument(..., help="Transform slug to remove"),
) -> None:
    """Remove an installed transform."""
    cfg = _cli_config()
    registry = _get_registry(cfg)
    _run(registry.fetch_index())
    installer = _get_installer(registry, cfg)

    try:
        installer.remove(slug)
    except InstallError as exc:
        typer.echo(f"  Error: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(f"  {slug} removed successfully.")
    typer.echo("  Restart backend if this plugin was loaded in memory.")


@app.command()
def info(
    slug: str = typer.Argument(..., help="Transform slug to inspect"),
) -> None:
    """Show detailed info for a transform."""
    cfg = _cli_config()
    registry = _get_registry(cfg)
    _run(registry.fetch_index())

    meta = registry.get_transform(slug)
    if meta is None:
        typer.echo(f"  Transform '{slug}' not found in registry.", err=True)
        raise typer.Exit(1)

    typer.echo(f"\n  {meta.get('display_name', slug)}")
    typer.echo(f"  {'─' * 40}")
    typer.echo(f"  Slug:         {meta.get('slug', '')}")
    typer.echo(f"  Version:      {meta.get('version', '')}")
    typer.echo(f"  Author:       {meta.get('author', '')} (@{meta.get('author_github', '')})")
    typer.echo(f"  Category:     {meta.get('category', '')}")
    typer.echo(f"  License:      {meta.get('license', '')}")
    typer.echo(f"  Tier:         {meta.get('verification_tier', '')}")
    typer.echo(f"  Description:  {meta.get('description', '')}")

    input_types = meta.get("input_types", [])
    output_types = meta.get("output_types", [])
    if input_types:
        typer.echo(f"  Input types:  {', '.join(input_types)}")
    if output_types:
        typer.echo(f"  Output types: {', '.join(output_types)}")

    deps = meta.get("python_dependencies", [])
    if deps:
        typer.echo(f"  Dependencies: {', '.join(deps)}")

    api_keys = meta.get("api_keys_required", [])
    if api_keys:
        typer.echo("  API keys:")
        for key_info in api_keys:
            typer.echo(f"    - {key_info.get('service', '')}: {key_info.get('env_var', '')}")

    pop = meta.get("popularity", {})
    if pop:
        typer.echo(f"  Popularity:   score={pop.get('computed_score', 0)}, "
                    f"up={pop.get('thumbs_up', 0)}, down={pop.get('thumbs_down', 0)}")

    typer.echo("")
