"""GitHub-based registry client.

Fetches the ``index.json`` from the registry repository, caches it
locally, and provides helpers for searching and downloading transforms.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import timedelta
from pathlib import Path
from typing import TypedDict

import httpx
from ogi.config import settings

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_REPO = "opengraphintel/ogi-transforms"
DEFAULT_CACHE_TTL = timedelta(hours=1)
DEFAULT_POPULARITY_CACHE_TTL = timedelta(minutes=10)

_SLUG_RE = re.compile(r"\*\*Slug:\*\*\s*`([^`]+)`")


class PopularityData(TypedDict, total=False):
    thumbs_up: int
    thumbs_down: int
    total_contributors: int
    commits_last_90_days: int
    discussion_url: str
    computed_score: int


class DynamicPopularityData(TypedDict, total=False):
    thumbs_up: int
    thumbs_down: int
    discussion_url: str


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
        self._popularity_cache_ttl = DEFAULT_POPULARITY_CACHE_TTL
        self._dynamic_popularity: dict[str, DynamicPopularityData] = {}
        self._dynamic_popularity_at: float = 0.0

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

    async def get_dynamic_popularity(
        self,
        slugs: set[str],
        force: bool = False,
    ) -> dict[str, DynamicPopularityData]:
        """Return per-slug dynamic popularity from GitHub Discussions with TTL cache."""
        now = time.time()
        if (
            not force
            and self._dynamic_popularity
            and (now - self._dynamic_popularity_at) < self._popularity_cache_ttl.total_seconds()
        ):
            return self._dynamic_popularity

        try:
            popularity = await self._fetch_discussions_popularity(slugs)
            self._dynamic_popularity = popularity
            self._dynamic_popularity_at = now
            return popularity
        except Exception as exc:
            logger.warning("Failed to fetch dynamic popularity data: %s", exc)
            if self._dynamic_popularity:
                return self._dynamic_popularity
            return {}

    async def apply_dynamic_popularity(
        self,
        index: RegistryIndex,
        force: bool = False,
    ) -> RegistryIndex:
        """Return a copy of index with dynamic thumbs/discussion_url and recomputed score."""
        transforms = index.get("transforms", [])
        slugs = {t.get("slug", "") for t in transforms if t.get("slug")}
        dynamic = await self.get_dynamic_popularity(slugs, force=force)

        merged_transforms: list[RegistryTransform] = []
        for transform in transforms:
            merged_transform: RegistryTransform = dict(transform)
            static_pop = transform.get("popularity", {})
            merged_pop: PopularityData = dict(static_pop) if static_pop else {}

            slug = transform.get("slug", "")
            override = dynamic.get(slug, {})
            if override:
                merged_pop["thumbs_up"] = int(override.get("thumbs_up", 0))
                merged_pop["thumbs_down"] = int(override.get("thumbs_down", 0))
                merged_pop["discussion_url"] = str(override.get("discussion_url", ""))

            thumbs_up = int(merged_pop.get("thumbs_up", 0))
            thumbs_down = int(merged_pop.get("thumbs_down", 0))
            contributors = int(merged_pop.get("total_contributors", 0))
            recent_commits = int(merged_pop.get("commits_last_90_days", 0))
            merged_pop["computed_score"] = (thumbs_up * 2) + (contributors * 3) + recent_commits - thumbs_down

            merged_transform["popularity"] = merged_pop
            merged_transforms.append(merged_transform)

        payload: RegistryIndex = dict(index)
        payload["transforms"] = merged_transforms
        return payload

    def search(
        self,
        query: str,
        category: str | None = None,
        tier: str | None = None,
    ) -> list[RegistryTransform]:
        """Filter cached index by query string, category, and/or tier."""
        if self._index is None:
            return []

        return self.search_in_index(self._index, query, category=category, tier=tier)

    def search_in_index(
        self,
        index: RegistryIndex,
        query: str,
        category: str | None = None,
        tier: str | None = None,
    ) -> list[RegistryTransform]:
        """Filter a provided index by query string, category, and/or tier."""
        results: list[RegistryTransform] = []
        q = query.lower()
        transforms = index.get("transforms", [])
        for transform in transforms:
            if category and transform.get("category", "") != category:
                continue
            if tier and transform.get("verification_tier", "") != tier:
                continue

            searchable = " ".join([
                transform.get("slug", ""),
                transform.get("name", ""),
                transform.get("display_name", ""),
                transform.get("description", ""),
                " ".join(transform.get("tags", [])),
                transform.get("category", ""),
                transform.get("author", ""),
            ]).lower()

            if q and q not in searchable:
                continue
            results.append(transform)

        return results

    async def _fetch_discussions_popularity(
        self,
        slugs: set[str],
    ) -> dict[str, DynamicPopularityData]:
        owner, name = self.repo.split("/", 1)
        query = """
        query($owner: String!, $name: String!, $after: String) {
          repository(owner: $owner, name: $name) {
            discussions(first: 100, after: $after) {
              pageInfo { hasNextPage endCursor }
              nodes {
                title
                url
                body
                reactionGroups {
                  content
                  users { totalCount }
                }
              }
            }
          }
        }
        """
        headers = {"Content-Type": "application/json"}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"

        popularity: dict[str, DynamicPopularityData] = {}
        after: str | None = None
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                variables: dict[str, str | None] = {"owner": owner, "name": name, "after": after}
                resp = await client.post(
                    "https://api.github.com/graphql",
                    headers=headers,
                    json={"query": query, "variables": variables},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("errors"):
                    raise RuntimeError(f"GitHub GraphQL errors: {data['errors']}")

                discussions = (
                    data.get("data", {})
                    .get("repository", {})
                    .get("discussions", {})
                )
                nodes = discussions.get("nodes", [])
                for node in nodes:
                    slug = self._extract_discussion_slug(node.get("body", ""), slugs)
                    if not slug:
                        continue

                    thumbs_up = 0
                    thumbs_down = 0
                    for group in node.get("reactionGroups", []):
                        content = group.get("content", "")
                        count = int(group.get("users", {}).get("totalCount", 0))
                        if content == "THUMBS_UP":
                            thumbs_up = count
                        elif content == "THUMBS_DOWN":
                            thumbs_down = count

                    popularity[slug] = DynamicPopularityData(
                        thumbs_up=thumbs_up,
                        thumbs_down=thumbs_down,
                        discussion_url=node.get("url", ""),
                    )

                page_info = discussions.get("pageInfo", {})
                if not page_info.get("hasNextPage"):
                    break
                after = page_info.get("endCursor")
                if not after:
                    break

        return popularity

    @staticmethod
    def _extract_discussion_slug(body: str, slugs: set[str]) -> str | None:
        match = _SLUG_RE.search(body or "")
        if not match:
            return None
        slug = match.group(1).strip()
        if slug in slugs:
            return slug
        return None

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
        files = [p for p in directory.rglob("*") if p.is_file()]
        for file_path in sorted(files, key=lambda p: p.relative_to(directory).as_posix()):
            rel = file_path.relative_to(directory)
            # Normalize separators and sorting key for cross-platform stability.
            hasher.update(rel.as_posix().encode())
            hasher.update(file_path.read_bytes())
        return hasher.hexdigest()
