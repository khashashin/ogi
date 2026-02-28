import asyncio

import httpx

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig

PLATFORMS: list[dict[str, str]] = [
    {"name": "GitHub", "url": "https://github.com/{username}"},
    {"name": "Reddit", "url": "https://www.reddit.com/user/{username}"},
    {"name": "Keybase", "url": "https://keybase.io/{username}"},
]


class UsernameSearch(BaseTransform):
    name = "username_search"
    display_name = "Username Search"
    description = "Checks popular platforms for username existence"
    input_types = [EntityType.SOCIAL_MEDIA, EntityType.PERSON]
    output_types = [EntityType.SOCIAL_MEDIA, EntityType.URL]
    category = "Social Media"

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        username = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        async with httpx.AsyncClient(
            timeout=5.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as client:
            for i, platform in enumerate(PLATFORMS):
                if i > 0:
                    await asyncio.sleep(0.5)

                profile_url = platform["url"].format(username=username)
                platform_name = platform["name"]

                try:
                    response = await client.head(profile_url)

                    if response.status_code == 200:
                        social_entity = Entity(
                            type=EntityType.SOCIAL_MEDIA,
                            value=f"{username}@{platform_name}",
                            properties={
                                "platform": platform_name,
                                "username": username,
                                "profile_url": profile_url,
                            },
                            source=self.name,
                        )
                        entities.append(social_entity)
                        edges.append(Edge(
                            source_id=entity.id,
                            target_id=social_entity.id,
                            label="has account",
                            source_transform=self.name,
                        ))

                        url_entity = Entity(
                            type=EntityType.URL,
                            value=profile_url,
                            properties={
                                "platform": platform_name,
                                "username": username,
                            },
                            source=self.name,
                        )
                        entities.append(url_entity)
                        edges.append(Edge(
                            source_id=social_entity.id,
                            target_id=url_entity.id,
                            label="profile URL",
                            source_transform=self.name,
                        ))

                        messages.append(f"Found {platform_name} account: {profile_url}")
                    else:
                        messages.append(
                            f"{platform_name}: not found (HTTP {response.status_code})"
                        )

                except httpx.TimeoutException:
                    messages.append(f"{platform_name}: request timed out")
                except httpx.RequestError as e:
                    messages.append(f"{platform_name}: request error - {e}")
                except Exception as e:
                    messages.append(f"{platform_name}: unexpected error - {e}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
