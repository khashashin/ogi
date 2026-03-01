"""``ogi transform`` sub-commands for the CLI."""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from ogi.cli.registry import RegistryClient
from ogi.cli.installer import TransformInstaller, InstallError

app = typer.Typer(help="Manage transforms from the OGI registry.")


def _get_registry() -> RegistryClient:
    return RegistryClient()


def _get_installer(registry: RegistryClient) -> TransformInstaller:
    plugins_dir = Path("plugins").resolve()
    plugins_dir.mkdir(parents=True, exist_ok=True)
    return TransformInstaller(registry, plugins_dir)


def _run(coro: object) -> object:
    return asyncio.get_event_loop().run_until_complete(coro)  # type: ignore[arg-type]


@app.command()
def search(
    query: str = typer.Argument("", help="Search query (name, tag, description)"),
    category: str | None = typer.Option(None, "--category", "-c", help="Filter by category"),
) -> None:
    """Search for transforms in the registry."""
    registry = _get_registry()
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
    registry = _get_registry()
    _run(registry.fetch_index())
    installer = _get_installer(registry)

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

    typer.echo(f"  {slug} installed successfully.\n")


@app.command("list")
def list_transforms() -> None:
    """List installed and available transforms."""
    registry = _get_registry()
    _run(registry.fetch_index())
    installer = _get_installer(registry)

    installed = installer.list_installed()
    all_transforms = registry.search("")

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

    available = [t for t in all_transforms if t.get("slug", "") not in installed and not t.get("bundled")]
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

    typer.echo(f"\n  {len(installed)} installed, {len(available)} available.\n")


@app.command()
def update(
    slug: str | None = typer.Argument(None, help="Transform slug to update (all if omitted)"),
) -> None:
    """Update installed transforms to the latest version."""
    registry = _get_registry()
    _run(registry.fetch_index())
    installer = _get_installer(registry)

    if slug:
        try:
            updated = _run(installer.update(slug))
        except InstallError as exc:
            typer.echo(f"  Error: {exc}", err=True)
            raise typer.Exit(1)
        if updated:
            typer.echo(f"  {slug} updated successfully.")
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
                _run(installer.update(s))
            except InstallError as exc:
                typer.echo(f"    Error updating {s}: {exc}", err=True)


@app.command()
def remove(
    slug: str = typer.Argument(..., help="Transform slug to remove"),
) -> None:
    """Remove an installed transform."""
    registry = _get_registry()
    _run(registry.fetch_index())
    installer = _get_installer(registry)

    try:
        installer.remove(slug)
    except InstallError as exc:
        typer.echo(f"  Error: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(f"  {slug} removed successfully.")


@app.command()
def info(
    slug: str = typer.Argument(..., help="Transform slug to inspect"),
) -> None:
    """Show detailed info for a transform."""
    registry = _get_registry()
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
