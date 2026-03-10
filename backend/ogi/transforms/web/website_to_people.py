import json
import re
from urllib.parse import urljoin, urlparse

import httpx

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig, TransformSetting


class WebsiteToPeople(BaseTransform):
    name = "website_to_people"
    display_name = "Website to People"
    description = "Finds people listed on a website's team/about pages and extracts them using OpenAI."
    input_types = [EntityType.DOMAIN, EntityType.URL]
    output_types = [EntityType.PERSON]
    category = "People"
    settings = [
        TransformSetting(
            name="openai_api_key",
            display_name="OpenAI API Key",
            description="Required OpenAI API key used to extract people from webpage content.",
            required=True,
            field_type="secret",
        ),
        TransformSetting(
            name="openai_model",
            display_name="OpenAI Model",
            description="Model used for extraction.",
            default="gpt-4.1-mini",
            field_type="select",
            options=["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o"],
        ),
        TransformSetting(
            name="max_people",
            display_name="Max People",
            description="Maximum number of people to return (1-500).",
            default="500",
            field_type="integer",
            min_value=1,
            max_value=500,
        ),
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        api_key = config.settings.get("openai_api_key", "").strip()
        if not api_key:
            return TransformResult(messages=["OpenAI API key required. Save it in API Keys (service: openai)."])

        model = config.settings.get("openai_model", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
        max_people = self.parse_int_setting(
            config.settings.get("max_people", "500"),
            setting_name="max_people",
            default=500,
            min_value=1,
            declared_max=500,
        )

        base_url = self._resolve_base_url(entity)
        if not base_url:
            return TransformResult(
                messages=[
                    "No valid website found for this entity.",
                    "Use a domain or website URL as the input entity.",
                ]
            )

        team_pages = await self._discover_people_pages(base_url)
        if not team_pages:
            return TransformResult(messages=[f"No people/team pages discovered from {base_url}."])

        page_texts: list[str] = []
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for page_url in team_pages:
                try:
                    resp = await client.get(page_url)
                    if resp.status_code != 200:
                        continue
                    text = self._html_to_text(resp.text)
                    if text:
                        page_texts.append(f"URL: {page_url}\n{text[:8000]}")
                except Exception:
                    continue

        if not page_texts:
            return TransformResult(messages=["People pages were found, but page text could not be fetched."])

        people = await self._extract_people_with_openai(
            api_key=api_key,
            model=model,
            website=base_url,
            page_chunks=page_texts,
            max_people=max_people,
        )
        if not people:
            return TransformResult(messages=["No people extracted from discovered pages."])

        entities: list[Entity] = []
        edges: list[Edge] = []
        seen_names: set[str] = set()
        for person_data in people[:max_people]:
            name = person_data.get("name", "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen_names:
                continue
            seen_names.add(key)

            role = person_data.get("role", "").strip()
            profile_url = person_data.get("profile_url", "").strip()
            person = Entity(
                type=EntityType.PERSON,
                value=name,
                project_id=entity.project_id,
                source=self.name,
                properties={
                    "website": base_url,
                    "role": role,
                    "profile_url": profile_url,
                    "source_transform": self.name,
                },
            )
            entities.append(person)
            edges.append(
                Edge(
                    source_id=entity.id,
                    target_id=person.id,
                    label="listed_on_website",
                    source_transform=self.name,
                )
            )

        return TransformResult(
            entities=entities,
            edges=edges,
            messages=[
                f"Website: {base_url}.",
                f"Scanned {len(page_texts)} page(s).",
                f"Extracted {len(entities)} people.",
            ],
        )

    def _resolve_base_url(self, entity: Entity) -> str | None:
        props = entity.properties or {}
        candidate = str(props.get("website") or props.get("url") or props.get("homepage") or entity.value or "").strip()
        return self._normalize_website_candidate(candidate)

    def _normalize_website_candidate(self, raw: str) -> str | None:
        candidate = raw.strip()
        if not candidate:
            return None
        if not candidate.startswith(("http://", "https://")):
            candidate = f"https://{candidate}"
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").strip().lower()
        if not self._is_valid_host(host):
            return None
        return f"{parsed.scheme}://{host}"

    def _is_valid_host(self, host: str) -> bool:
        if not host or len(host) > 253:
            return False
        if "," in host or "_" in host:
            return False
        if host.startswith(".") or host.endswith("."):
            return False
        labels = host.split(".")
        if len(labels) < 2:
            return False
        for label in labels:
            if not label or len(label) > 63:
                return False
            if label.startswith("-") or label.endswith("-"):
                return False
            if not re.fullmatch(r"[a-z0-9-]+", label):
                return False
        return re.fullmatch(r"[a-z]{2,63}", labels[-1]) is not None

    async def _discover_people_pages(self, base_url: str) -> list[str]:
        candidates: set[str] = set()
        keywords = ("team", "about", "people", "leadership", "staff", "company")
        static_paths = [
            "/team",
            "/about/team",
            "/about-us/team",
            "/about",
            "/people",
            "/leadership",
            "/company",
        ]

        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            for path in static_paths:
                url = urljoin(base_url + "/", path.lstrip("/"))
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        candidates.add(url)
                except Exception:
                    continue

            try:
                home = await client.get(base_url)
                if home.status_code == 200:
                    for href in re.findall(r'href=["\']([^"\']+)["\']', home.text, flags=re.IGNORECASE):
                        full = urljoin(base_url + "/", href)
                        parsed = urlparse(full)
                        if not parsed.netloc or parsed.netloc != urlparse(base_url).netloc:
                            continue
                        lower = full.lower()
                        if any(keyword in lower for keyword in keywords):
                            candidates.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
            except Exception:
                pass

        return sorted(candidates)[:8]

    def _html_to_text(self, html: str) -> str:
        no_script = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        no_style = re.sub(r"(?is)<style.*?>.*?</style>", " ", no_script)
        text = re.sub(r"(?s)<[^>]+>", " ", no_style)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    async def _extract_people_with_openai(
        self,
        *,
        api_key: str,
        model: str,
        website: str,
        page_chunks: list[str],
        max_people: int,
    ) -> list[dict[str, str]]:
        prompt = (
            "Extract people listed on the supplied website/team page text. "
            f"Website: {website}. "
            'Return strict JSON only with schema {"people":[{"name":"", "role":"", "profile_url":""}]}. '
            f"Return at most {max_people} unique real people. "
            "Do not include advisors, investors, companies, or placeholders. "
            "If uncertain, omit the entry."
        )
        input_text = "\n\n".join(page_chunks[:8])[:60000]

        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": "You extract structured data."}]},
                {"role": "user", "content": [{"type": "input_text", "text": prompt + "\n\n" + input_text}]},
            ],
            "text": {"format": {"type": "json_object"}},
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        raw = self._response_text(data).strip()
        if not raw:
            return []
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.replace("json", "", 1).strip()

        parsed = json.loads(raw)
        people = parsed.get("people") or parsed.get("members") or []
        if not isinstance(people, list):
            return []
        out: list[dict[str, str]] = []
        for item in people:
            if not isinstance(item, dict):
                continue
            out.append(
                {
                    "name": str(item.get("name", "")),
                    "role": str(item.get("role", "")),
                    "profile_url": str(item.get("profile_url", "")),
                }
            )
        return out

    def _response_text(self, payload: dict) -> str:
        direct = payload.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct

        fragments: list[str] = []
        for item in payload.get("output", []) or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []) or []:
                if not isinstance(content, dict):
                    continue
                text_value = content.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    fragments.append(text_value)
        return "\n".join(fragments)
