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


class EmailToHolehe(BaseTransform):
    name = "email_to_holehe"
    display_name = "Email to Holehe"
    description = "Imports Holehe email-registration evidence into the graph from pasted JSON output"
    input_types = [EntityType.EMAIL_ADDRESS]
    output_types = [EntityType.SOCIAL_MEDIA, EntityType.URL, EntityType.DOCUMENT]
    category = "People"
    settings = [
        TransformSetting(
            name="result_json",
            display_name="Holehe JSON Output",
            description="JSON output captured from an external Holehe run.",
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
            description="Optional Holehe version string.",
            default="",
            field_type="string",
        ),
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        email = entity.value.strip()
        timestamp = source_timestamp(config)
        payload, error = load_fixture_payload(config)
        command = f"holehe {email}"
        if error:
            return TransformResult(messages=[error, f"Run externally and paste JSON output: {command}"])

        warning = (
            "Holehe uses registration and recovery flows that may change or rate-limit; "
            "treat matches as leads until independently verified."
        )
        entities: list[Entity] = []
        edges: list[Edge] = []
        matches = 0

        for service_name, record in result_items(payload):
            service = self._service_name(service_name, record)
            if not service or not is_positive_match(record):
                continue
            matches += 1
            profile_url = first_present(record, ["url", "profile_url", "link", "uri"])
            props = provenance_properties(
                tool_name="holehe",
                command=command,
                source_timestamp=timestamp,
                tool_version=config.settings.get("tool_version", ""),
                confidence=0.85,
                raw_match_url=profile_url,
                warning=warning,
                raw_record=record,
            )
            props.update({
                "service": service,
                "email": email,
                "email_recovery": str(first_present(record, ["emailrecovery", "email_recovery"], "")),
                "phone_recovery": str(first_present(record, ["phoneNumber", "phone_number"], "")),
                "rate_limited": bool(record.get("rateLimit") or record.get("rate_limited")),
            })

            social = Entity(
                type=EntityType.SOCIAL_MEDIA,
                value=f"{email}@{service}",
                properties=props,
                source=self.name,
            )
            entities.append(social)
            edges.append(Edge(
                source_id=entity.id,
                target_id=social.id,
                label="registered account",
                source_transform=self.name,
            ))

            if profile_url:
                url_entity = Entity(
                    type=EntityType.URL,
                    value=profile_url,
                    properties=props | {"url_type": "service profile"},
                    source=self.name,
                )
                entities.append(url_entity)
                edges.append(Edge(
                    source_id=social.id,
                    target_id=url_entity.id,
                    label="profile URL",
                    source_transform=self.name,
                ))

        if matches:
            doc = fixture_document(
                tool_name="Holehe",
                subject=email,
                match_count=matches,
                properties=provenance_properties(
                    tool_name="holehe",
                    command=command,
                    source_timestamp=timestamp,
                    tool_version=config.settings.get("tool_version", ""),
                    confidence=0.85,
                    warning=warning,
                ),
                source=self.name,
            )
            entities.append(doc)
            edges.append(Edge(source_id=entity.id, target_id=doc.id, label="tool evidence", source_transform=self.name))

        suffix = "match" if matches == 1 else "matches"
        return TransformResult(entities=entities, edges=edges, messages=[f"Holehe fixture produced {matches} account {suffix}."])

    @staticmethod
    def _service_name(key: str, record: dict[str, Any]) -> str:
        return str(first_present(record, ["name", "site", "service", "platform"], key)).strip()
