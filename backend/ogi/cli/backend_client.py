"""Best-effort backend calls used by CLI commands."""
from __future__ import annotations

import os

import httpx

from ogi.cli.user_config import ConfigDict


def _api_base_url(cfg: ConfigDict) -> str:
    cli_cfg = cfg.get("cli", {})
    if isinstance(cli_cfg, dict):
        raw = str(cli_cfg.get("api_base_url", "http://localhost:8000/api/v1")).strip()
    else:
        raw = "http://localhost:8000/api/v1"
    return raw.rstrip("/")


def _auth_header() -> dict[str, str]:
    token = os.environ.get("OGI_CLI_BEARER_TOKEN", "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


async def try_reload_plugin(slug: str, cfg: ConfigDict) -> tuple[bool, str]:
    """Try to reload a plugin in a running backend without failing the CLI flow."""
    url = f"{_api_base_url(cfg)}/plugins/{slug}/reload"
    headers = _auth_header()

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0)) as client:
            resp = await client.post(url, headers=headers)
    except Exception:
        return (False, "Backend not reachable; restart backend to load this plugin.")

    if resp.status_code in (200, 201):
        return (True, f"Reloaded plugin '{slug}' in running backend.")
    if resp.status_code in (401, 403):
        return (
            False,
            "Installed locally, but backend reload was unauthorized. "
            "Set OGI_CLI_BEARER_TOKEN or run in local auth-bypass mode.",
        )
    if resp.status_code == 404:
        return (False, "Installed locally. Backend did not find plugin to reload yet; restart backend.")
    return (False, f"Installed locally, but backend reload failed ({resp.status_code}).")
