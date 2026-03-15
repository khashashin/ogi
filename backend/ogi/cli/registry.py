"""GitHub-based registry client.

Fetches the ``index.json`` from the registry repository, caches it
locally, and provides helpers for searching and downloading transforms.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import timedelta
from pathlib import Path
from typing import TypedDict

import httpx
from ogi.config import settings

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_REPO = "opengraphintel/ogi-transforms"
DEFAULT_CACHE_TTL = timedelta(hours=1)


class PopularityData(TypedDict, total=False):
    thumbs_up: int
    thumbs_down: int
    total_contributors: int
    commits_last_90_days: int
    discussion_url: str
    computed_score: int


class RegistryTransform(TypedDict, total=False):
    slug: str
    name: str
    display_name: str
    description: str
    version: str
    author: str
    author_github: str
    license: str
    category: str
    input_types: list[str]
    output_types: list[str]
    min_ogi_version: str
    max_ogi_version: str | None
    python_dependencies: list[str]
    api_keys_required: list[dict[str, str]]
    tags: list[str]
    verification_tier: str
    bundled: bool
    download_url: str
    readme_url: str
    sha256: str
    permissions: dict[str, bool]
    popularity: PopularityData
    icon: str
    color: str
    created_at: str
    updated_at: str


class RegistryIndex(TypedDict, total=False):
    version: int
    generated_at: str
    repo: str
    transforms: list[RegistryTransform]


class RegistryClient:
    """Fetches, caches, and queries the OGI transform registry."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        repo: str = DEFAULT_REGISTRY_REPO,
        cache_ttl: timedelta = DEFAULT_CACHE_TTL,
    ) -> None:
        self.repo = repo
        self.cache_ttl = cache_ttl
        if cache_dir is None:
            cache_dir = Path.home() / ".ogi" / "cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index: RegistryIndex | None = None

    @property
    def _index_url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.repo}/main/index.json"

    @property
    def _cache_path(self) -> Path:
        return self.cache_dir / "index.json"

    @property
    def _etag_path(self) -> Path:
        return self.cache_dir / "index_etag"

    def _is_cache_fresh(self) -> bool:
        if not self._cache_path.exists():
            return False
        age = time.time() - self._cache_path.stat().st_mtime
        return age < self.cache_ttl.total_seconds()

    async def fetch_index(self, force: bool = False) -> RegistryIndex:
        """Fetch index.json, using local cache if fresh."""
        if not force and self._is_cache_fresh() and self._index is not None:
            return self._index

        if not force and self._is_cache_fresh():
            try:
                with open(self._cache_path) as f:
                    self._index = json.load(f)
                return self._index  # type: ignore[return-value]
            except Exception:
                pass  # fall through to network fetch

        headers: dict[str, str] = {}
        if self._etag_path.exists():
            headers["If-None-Match"] = self._etag_path.read_text().strip()
            
        if settings.github_token:
            headers["Authorization"] = f"token {settings.github_token}"

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(self._index_url, headers=headers)
                if resp.status_code == 304 and self._cache_path.exists():
                    with open(self._cache_path) as f:
                        self._index = json.load(f)
                    return self._index  # type: ignore[return-value]
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                err_body = ""
                if hasattr(exc, "response") and exc.response is not None:
                    err_body = exc.response.text
                logger.warning(
                    "Failed to fetch registry index: %s (Response: %s)", 
                    exc, err_body
                )
                if self._cache_path.exists():
                    with open(self._cache_path) as f:
                        self._index = json.load(f)
                    return self._index  # type: ignore[return-value]
                return RegistryIndex(version=2, generated_at="", repo=self.repo, transforms=[])

        self._index = resp.json()

        # Persist cache
        with open(self._cache_path, "w") as f:
            json.dump(self._index, f)
        etag = resp.headers.get("etag")
        if etag:
            self._etag_path.write_text(etag)

        return self._index  # type: ignore[return-value]

    def get_cached_index(self) -> RegistryIndex | None:
        """Return in-memory index without fetching."""
        return self._index

    def search(
        self,
        query: str,
        category: str | None = None,
        tier: str | None = None,
    ) -> list[RegistryTransform]:
        """Filter cached index by query string, category, and/or tier."""
        if self._index is None:
            return []

        results: list[RegistryTransform] = []
        q = query.lower()
        # index.json is a dict with a 'transforms' key containing the list
        transforms = self._index.get("transforms", [])
        for t in transforms:
            if category and t.get("category", "") != category:
                continue
            if tier and t.get("verification_tier", "") != tier:
                continue

            searchable = " ".join([
                t.get("slug", ""),
                t.get("name", ""),
                t.get("display_name", ""),
                t.get("description", ""),
                " ".join(t.get("tags", [])),
                t.get("category", ""),
                t.get("author", ""),
            ]).lower()

            if q and q not in searchable:
                continue
            results.append(t)

        return results

    def get_transform(self, slug: str) -> RegistryTransform | None:
        """Look up a single transform by slug."""
        if self._index is None:
            return None
        transforms = self._index.get("transforms", [])
        for t in transforms:
            if t.get("slug") == slug:
                return t
        return None

    async def download_transform(
        self,
        slug: str,
        category: str,
        target_dir: Path,
    ) -> list[str]:
        """Download transform files from GitHub Contents API.

        Returns a list of relative file paths that were downloaded.
        """
        contents_url = (
            f"https://api.github.com/repos/{self.repo}"
            f"/contents/transforms/{category}/{slug}"
        )
        downloaded_files: list[str] = []
        
        headers: dict[str, str] = {}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"

        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            await self._download_directory(
                client, contents_url, target_dir, "", downloaded_files
            )

        return downloaded_files

    async def _download_directory(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        target_dir: Path,
        relative_prefix: str,
        downloaded_files: list[str],
    ) -> None:
        """Recursively download a directory from the GitHub Contents API."""
        resp = await client.get(api_url)
        resp.raise_for_status()
        items: list[dict[str, str]] = resp.json()

        for item in items:
            item_type = item.get("type", "")
            item_name = item.get("name", "")
            rel_path = f"{relative_prefix}{item_name}" if not relative_prefix else f"{relative_prefix}/{item_name}"

            if item_type == "file":
                download_url = item.get("download_url", "")
                if download_url:
                    file_resp = await client.get(download_url)
                    file_resp.raise_for_status()
                    dest = target_dir / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(file_resp.content)
                    downloaded_files.append(rel_path)
            elif item_type == "dir":
                sub_url = item.get("url", "")
                if sub_url:
                    await self._download_directory(
                        client, sub_url, target_dir, rel_path, downloaded_files
                    )

    @staticmethod
    def compute_sha256(directory: Path) -> str:
        """Compute a deterministic SHA256 over all files in *directory*."""
        hasher = hashlib.sha256()
        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file():
                rel = file_path.relative_to(directory)
                hasher.update(str(rel).encode())
                hasher.update(file_path.read_bytes())
        return hasher.hexdigest()
