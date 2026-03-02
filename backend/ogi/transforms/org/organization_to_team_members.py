import json
import re
from urllib.parse import urljoin, urlparse

import httpx

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig, TransformSetting


class OrganizationToTeamMembers(BaseTransform):
    name = "organization_to_team_members"
    display_name = "Organization to Team Members"
    description = "Finds an organization's team pages and extracts up to 500 team members using OpenAI."
    input_types = [EntityType.ORGANIZATION]
    output_types = [EntityType.PERSON]
    category = "People"
    settings = [
        TransformSetting(
            name="openai_api_key",
            display_name="OpenAI API Key",
            description="Required OpenAI API key used to extract team members from webpage content.",
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
            name="max_members",
            display_name="Max Members",
            description="Maximum number of team members to return (1-500).",
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
        max_members = self._parse_max_members(config.settings.get("max_members", "500"))

        base_url = self._resolve_website(entity)
        if not base_url:
            return TransformResult(
                messages=["No website found for this organization. Add a website/domain in entity properties."]
            )

        team_pages = await self._discover_team_pages(base_url)
        if not team_pages:
            return TransformResult(messages=[f"No team pages discovered from {base_url}."])

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
            return TransformResult(messages=["Team pages were found, but page text could not be fetched."])

        members = await self._extract_members_with_openai(
            api_key=api_key,
            model=model,
            organization_name=entity.value,
            page_chunks=page_texts,
            max_members=max_members,
        )
        if not members:
            return TransformResult(messages=["No team members extracted from discovered pages."])

        entities: list[Entity] = []
        edges: list[Edge] = []
        seen_names: set[str] = set()
        for member in members[:max_members]:
            name = member.get("name", "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen_names:
                continue
            seen_names.add(key)

            role = member.get("role", "").strip()
            profile_url = member.get("profile_url", "").strip()
            person = Entity(
                type=EntityType.PERSON,
                value=name,
                project_id=entity.project_id,
                source=self.name,
                properties={
                    "organization": entity.value,
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
                    label="team_member",
                    source_transform=self.name,
                )
            )

        return TransformResult(
            entities=entities,
            edges=edges,
            messages=[
                f"Scanned {len(page_texts)} page(s).",
                f"Extracted {len(entities)} team member(s).",
            ],
        )

    def _parse_max_members(self, value: str) -> int:
        try:
            parsed = int(value)
        except Exception:
            parsed = 500
        return max(1, min(parsed, 500))

    def _resolve_website(self, entity: Entity) -> str | None:
        props = entity.properties or {}
        raw = (
            str(props.get("website") or props.get("url") or props.get("homepage") or props.get("domain") or "").strip()
        )
        if not raw:
            raw = entity.value.strip()
        if not raw:
            return None
        if not raw.startswith(("http://", "https://")):
            raw = f"https://{raw}"
        parsed = urlparse(raw)
        if not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}"

    async def _discover_team_pages(self, base_url: str) -> list[str]:
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
                        if any(k in lower for k in keywords):
                            candidates.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
            except Exception:
                pass

        ordered = sorted(candidates)
        return ordered[:8]

    def _html_to_text(self, html: str) -> str:
        no_script = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        no_style = re.sub(r"(?is)<style.*?>.*?</style>", " ", no_script)
        text = re.sub(r"(?s)<[^>]+>", " ", no_style)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    async def _extract_members_with_openai(
        self,
        api_key: str,
        model: str,
        organization_name: str,
        page_chunks: list[str],
        max_members: int,
    ) -> list[dict[str, str]]:
        prompt = (
            "Extract team members from the supplied webpage text for organization "
            f"'{organization_name}'. Return strict JSON only with this schema: "
            '{"members":[{"name":"", "role":"", "profile_url":""}]}. '
            f"Return at most {max_members} unique real people. "
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

        raw = (data.get("output_text") or "").strip()
        if not raw:
            return []
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.replace("json", "", 1).strip()

        parsed = json.loads(raw)
        members = parsed.get("members", [])
        if not isinstance(members, list):
            return []
        out: list[dict[str, str]] = []
        for item in members:
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
