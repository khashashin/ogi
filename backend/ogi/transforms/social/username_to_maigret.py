from typing import Any

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig, TransformSetting
from ogi.transforms.user_osint import (
    fixture_document,
    first_present,
    is_positive_match,
    load_fixture_payload,
    provenance_properties,
    result_items,
    source_timestamp,
)


class UsernameToMaigret(BaseTransform):
    name = "username_to_maigret"
    display_name = "Username to Maigret"
    description = "Imports Maigret username-search evidence into the graph from pasted JSON output"
    input_types = [EntityType.USERNAME]
    output_types = [EntityType.SOCIAL_MEDIA, EntityType.URL, EntityType.DOCUMENT]
    category = "People"
    settings = [
        TransformSetting(
            name="result_json",
            display_name="Maigret JSON Output",
            description="JSON output captured from an external Maigret run.",
            default="",
            field_type="string",
        ),
        TransformSetting(
            name="source_timestamp",
            display_name="Source Timestamp",
            description="Timestamp for the imported tool output.",
            default="",
            field_type="string",
        ),
        TransformSetting(
            name="tool_version",
            display_name="Tool Version",
            description="Optional Maigret version string.",
            default="",
            field_type="string",
        ),
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        username = entity.value.strip()
        timestamp = source_timestamp(config)
        payload, error = load_fixture_payload(config)
        command = f"maigret {username} --json"
        if error:
            return TransformResult(messages=[error, f"Run externally and paste JSON output: {command}"])

        warning = (
            "Maigret checks public profiles at scale; results can be stale, rate-limited, "
            "or false-positive and should be verified before attribution."
        )
        entities: list[Entity] = []
        edges: list[Edge] = []
        matches = 0

        for platform_name, record in result_items(payload):
            platform = self._platform_name(platform_name, record)
            if not platform or not is_positive_match(record):
                continue
            profile_url = first_present(record, ["url_user", "profile_url", "url", "uri", "link"])
            if not profile_url:
                continue
            matches += 1
            matched_username = str(first_present(record, ["username", "account", "account_name"], username))
            props = provenance_properties(
                tool_name="maigret",
                command=command,
                source_timestamp=timestamp,
                tool_version=config.settings.get("tool_version", ""),
                confidence=0.95,
                raw_match_url=profile_url,
                warning=warning,
                raw_record=record,
            )
            props.update({
                "platform": platform,
                "username": matched_username,
                "site_tags": record.get("tags", []),
            })
            social = Entity(
                type=EntityType.SOCIAL_MEDIA,
                value=f"{matched_username}@{platform}",
                properties=props,
                source=self.name,
            )
            entities.append(social)
            edges.append(Edge(source_id=entity.id, target_id=social.id, label="found account", source_transform=self.name))

            url_entity = Entity(
                type=EntityType.URL,
                value=str(profile_url),
                properties=props | {"url_type": "profile"},
                source=self.name,
            )
            entities.append(url_entity)
            edges.append(Edge(source_id=social.id, target_id=url_entity.id, label="profile URL", source_transform=self.name))

        if matches:
            doc = fixture_document(
                tool_name="Maigret",
                subject=username,
                match_count=matches,
                properties=provenance_properties(
                    tool_name="maigret",
                    command=command,
                    source_timestamp=timestamp,
                    tool_version=config.settings.get("tool_version", ""),
                    confidence=0.95,
                    warning=warning,
                ),
                source=self.name,
            )
            entities.append(doc)
            edges.append(Edge(source_id=entity.id, target_id=doc.id, label="tool evidence", source_transform=self.name))

        suffix = "match" if matches == 1 else "matches"
        return TransformResult(entities=entities, edges=edges, messages=[f"Maigret fixture produced {matches} account {suffix}."])

    @staticmethod
    def _platform_name(key: str, record: dict[str, Any]) -> str:
        return str(first_present(record, ["site_name", "name", "site", "platform"], key)).strip()
