import asyncio
import random
import string
import time
from typing import Any

import httpx

from ogi.models import Edge, Entity, EntityType, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig, TransformSetting

WHATS_MY_NAME_URL = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
CATALOG_TTL_SECONDS = 24 * 60 * 60
SITE_VALIDATION_TTL_SECONDS = 72 * 60 * 60
FALLBACK_PLATFORMS: list[dict[str, Any]] = [
    {
        "name": "GitHub",
        "cat": "developer",
        "uri_check": "https://github.com/{account}",
        "uri_pretty": "https://github.com/{account}",
        "e_code": 200,
        "e_string": "",
        "must_have_name": True,
    },
    {
        "name": "Reddit",
        "cat": "community",
        "uri_check": "https://www.reddit.com/user/{account}",
        "uri_pretty": "https://www.reddit.com/user/{account}",
        "e_code": 200,
        "e_string": "",
        "must_have_name": True,
    },
    {
        "name": "Keybase",
        "cat": "developer",
        "uri_check": "https://keybase.io/{account}",
        "uri_pretty": "https://keybase.io/{account}",
        "e_code": 200,
        "e_string": "",
        "must_have_name": True,
    },
]
COMMON_NOISY_USERNAMES = {
    "admin",
    "contact",
    "guest",
    "hello",
    "info",
    "mail",
    "root",
    "sales",
    "support",
    "test",
    "user",
}


class UsernameSearch(BaseTransform):
    name = "username_search"
    display_name = "Username Search"
    description = "Checks social platforms for likely username existence using a cached site catalog"
    input_types = [EntityType.SOCIAL_MEDIA, EntityType.USERNAME]
    output_types = [EntityType.SOCIAL_MEDIA, EntityType.URL]
    category = "Social Media"
    settings = [
        TransformSetting(
            name="min_username_length",
            display_name="Minimum Username Length",
            description="Skip short usernames that produce too many false positives.",
            default="4",
            field_type="integer",
            min_value=1,
            max_value=64,
        ),
        TransformSetting(
            name="must_have_name",
            display_name="Require Username On Page",
            description="Only accept matches when the profile page mentions the username in its content.",
            default="true",
            field_type="boolean",
        ),
        TransformSetting(
            name="scan_permutations",
            display_name="Scan Similar Usernames",
            description="Also test a bounded set of common typo and separator variations.",
            default="false",
            field_type="boolean",
        ),
        TransformSetting(
            name="max_sites",
            display_name="Max Sites",
            description="Limit the number of catalog sites scanned per username.",
            default="25",
            field_type="integer",
            min_value=1,
            max_value=200,
        ),
        TransformSetting(
            name="concurrency",
            display_name="Concurrency",
            description="Maximum concurrent site checks.",
            default="10",
            field_type="integer",
            min_value=1,
            max_value=50,
        ),
    ]

    _catalog_cache: tuple[float, list[dict[str, Any]]] | None = None
    _trusted_sites_cache: tuple[float, list[dict[str, Any]]] | None = None

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        username = self._extract_username(entity)
        if not username:
            return TransformResult(messages=["No username value available for scanning."])

        min_len = self._get_int(config, "min_username_length", 4, 1, 64)
        if len(username) < min_len:
            return TransformResult(messages=[f"Skipped '{username}': below minimum username length {min_len}."])

        if username.lower() in COMMON_NOISY_USERNAMES:
            return TransformResult(messages=[f"Skipped '{username}': too generic for reliable account search."])

        must_have_name = self._get_bool(config, "must_have_name", True)
        scan_permutations = self._get_bool(config, "scan_permutations", False)
        max_sites = self._get_int(config, "max_sites", 25, 1, 200)
        concurrency = self._get_int(config, "concurrency", 10, 1, 50)

        candidates = [username]
        if scan_permutations:
            candidates.extend(self._generate_permutations(username))

        candidates = list(dict.fromkeys(candidates))[:6]

        sites, catalog_source = await self._get_candidate_sites(max_sites=max_sites)
        if not sites:
            return TransformResult(messages=["No site catalog available for username search."])

        entities: list[Entity] = []
        edges: list[Edge] = []
        messages = [f"Scanning {len(candidates)} username candidate(s) across {len(sites)} site(s) from {catalog_source}."]

        async with httpx.AsyncClient(
            timeout=6.0,
            follow_redirects=True,
            headers={"User-Agent": "OGI-UsernameSearch/1.0"},
        ) as client:
            results = await self._scan_candidates(
                client=client,
                candidates=candidates,
                sites=sites,
                concurrency=concurrency,
                must_have_name=must_have_name,
            )

        seen_social_values: set[str] = set()
        seen_urls: set[str] = set()
        found_count = 0
        for result in results:
            if not result["found"]:
                continue
            found_count += 1
            matched_username = result["matched_username"]
            platform_name = result["platform_name"]
            profile_url = result["profile_url"]
            social_value = f"{matched_username}@{platform_name}"
            if social_value not in seen_social_values:
                social_entity = Entity(
                    type=EntityType.SOCIAL_MEDIA,
                    value=social_value,
                    properties={
                        "platform": platform_name,
                        "username": matched_username,
                        "profile_url": profile_url,
                        "site_category": result["site_category"],
                        "account_match": "exact" if matched_username == username else "similar",
                    },
                    source=self.name,
                )
                entities.append(social_entity)
                edges.append(
                    Edge(
                        source_id=entity.id,
                        target_id=social_entity.id,
                        label="has account" if matched_username == username else "similar account",
                        source_transform=self.name,
                    )
                )
                seen_social_values.add(social_value)
            else:
                social_entity = next(e for e in entities if e.type == EntityType.SOCIAL_MEDIA and e.value == social_value)

            if profile_url not in seen_urls:
                url_entity = Entity(
                    type=EntityType.URL,
                    value=profile_url,
                    properties={
                        "platform": platform_name,
                        "username": matched_username,
                    },
                    source=self.name,
                )
                entities.append(url_entity)
                edges.append(
                    Edge(
                        source_id=social_entity.id,
                        target_id=url_entity.id,
                        label="profile URL",
                        source_transform=self.name,
                    )
                )
                seen_urls.add(profile_url)

            messages.append(f"Found {platform_name} account for {matched_username}: {profile_url}")

        if found_count == 0:
            messages.append("No matching accounts found in the scanned site set.")

        return TransformResult(entities=entities, edges=edges, messages=messages)

    def _extract_username(self, entity: Entity) -> str:
        if entity.type == EntityType.SOCIAL_MEDIA:
            username = entity.properties.get("username")
            if isinstance(username, str) and username.strip():
                return username.strip()
        return entity.value.strip()

    async def _get_candidate_sites(self, max_sites: int) -> tuple[list[dict[str, Any]], str]:
        sites, source = await self._load_site_catalog()
        trusted = await self._filter_untrusted_sites(sites)
        return trusted[:max_sites], source

    async def _load_site_catalog(self) -> tuple[list[dict[str, Any]], str]:
        now = time.time()
        if self._catalog_cache and (now - self._catalog_cache[0]) < CATALOG_TTL_SECONDS:
            return self._catalog_cache[1], "cache"

        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                response = await client.get(WHATS_MY_NAME_URL)
                response.raise_for_status()
                payload = response.json()
            sites = [
                site
                for site in payload.get("sites", [])
                if site.get("valid", True) is not False and site.get("uri_check")
            ]
            if sites:
                self.__class__._catalog_cache = (now, sites)
                return sites, "whatsmyname"
        except Exception:
            pass

        self.__class__._catalog_cache = (now, FALLBACK_PLATFORMS)
        return FALLBACK_PLATFORMS, "fallback"

    async def _filter_untrusted_sites(self, sites: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = time.time()
        if self._trusted_sites_cache and (now - self._trusted_sites_cache[0]) < SITE_VALIDATION_TTL_SECONDS:
            return self._trusted_sites_cache[1]

        probe = self._random_probe_username()
        async with httpx.AsyncClient(
            timeout=6.0,
            follow_redirects=True,
            headers={"User-Agent": "OGI-UsernameSearch/1.0"},
        ) as client:
            results = await self._scan_candidates(
                client=client,
                candidates=[probe],
                sites=sites[: min(len(sites), 40)],
                concurrency=8,
                must_have_name=True,
            )
        distrusted = {item["platform_name"] for item in results if item["found"]}
        trusted = [site for site in sites if site.get("name") not in distrusted]
        self.__class__._trusted_sites_cache = (now, trusted)
        return trusted

    async def _scan_candidates(
        self,
        *,
        client: httpx.AsyncClient,
        candidates: list[str],
        sites: list[dict[str, Any]],
        concurrency: int,
        must_have_name: bool,
    ) -> list[dict[str, Any]]:
        sem = asyncio.Semaphore(concurrency)
        tasks = [
            self._check_site(client, sem, candidate, site, must_have_name)
            for candidate in candidates
            for site in sites
        ]
        return await asyncio.gather(*tasks)

    async def _check_site(
        self,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        username: str,
        site: dict[str, Any],
        must_have_name: bool,
    ) -> dict[str, Any]:
        async with sem:
            template = site.get("uri_check")
            if not isinstance(template, str) or "{account}" not in template:
                return self._not_found(site, username, "unsupported site definition")

            profile_url = template.format(account=username)
            pretty_url = site.get("uri_pretty", profile_url)
            post_body = site.get("post_body")
            method = "POST" if post_body else "GET"

            try:
                response = await client.request(method, profile_url, data=post_body if post_body else None)
            except httpx.TimeoutException:
                return self._not_found(site, username, "request timed out")
            except httpx.RequestError as exc:
                return self._not_found(site, username, f"request error: {exc}")

            expected_code = site.get("e_code")
            if expected_code is not None and str(response.status_code) != str(expected_code):
                return self._not_found(site, username, f"HTTP {response.status_code}")

            body = response.text or ""
            expected_text = site.get("e_string")
            missing_text = site.get("m_string")

            if expected_text and expected_text not in body:
                return self._not_found(site, username, "match string missing")
            if missing_text and missing_text in body:
                return self._not_found(site, username, "missing-string marker present")
            if must_have_name and username.lower() not in body.lower():
                return self._not_found(site, username, "username absent from page content")
            if "." in username:
                first = username.split(".", 1)[0]
                lowered = body.lower()
                if f"{first}<" in lowered or f'{first}"' in lowered:
                    return self._not_found(site, username, "dot-username false-positive guard")

            return {
                "found": True,
                "platform_name": str(site.get("name", "Unknown")),
                "site_category": str(site.get("cat", "general")),
                "matched_username": username,
                "profile_url": pretty_url.format(account=username) if isinstance(pretty_url, str) else profile_url,
            }

    @staticmethod
    def _not_found(site: dict[str, Any], username: str, reason: str) -> dict[str, Any]:
        return {
            "found": False,
            "platform_name": str(site.get("name", "Unknown")),
            "site_category": str(site.get("cat", "general")),
            "matched_username": username,
            "profile_url": "",
            "reason": reason,
        }

    @staticmethod
    def _generate_permutations(username: str) -> list[str]:
        permutations: set[str] = set()
        replacements = {
            "a": ["4"],
            "e": ["3"],
            "i": ["1"],
            "l": ["1"],
            "o": ["0"],
            "s": ["5"],
            "t": ["7"],
        }
        separators = ["_", "-"]

        for idx, char in enumerate(username.lower()):
            for repl in replacements.get(char, []):
                permutations.add(username[:idx] + repl + username[idx + 1 :])

        for separator in separators:
            permutations.add(f"{username}{separator}")
            permutations.add(f"{separator}{username}")

        if "." not in username and len(username) >= 6:
            midpoint = len(username) // 2
            permutations.add(username[:midpoint] + "." + username[midpoint:])

        return [value for value in permutations if value != username and len(value) >= 4]

    @staticmethod
    def _random_probe_username() -> str:
        rand = random.SystemRandom()
        alphabet = string.ascii_lowercase + string.digits
        return "".join(rand.choice(alphabet) for _ in range(12))

    @staticmethod
    def _get_bool(config: TransformConfig, key: str, default: bool) -> bool:
        raw = config.settings.get(key)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _get_int(config: TransformConfig, key: str, default: int, minimum: int, maximum: int) -> int:
        raw = config.settings.get(key)
        if raw is None:
            return default
        try:
            parsed = int(raw)
        except ValueError:
            return default
        return max(minimum, min(maximum, parsed))
