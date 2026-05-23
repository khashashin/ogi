from typing import Any

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig, TransformSetting
from ogi.transforms.user_osint import (
    fixture_document,
    first_present,
    load_fixture_payload,
    provenance_properties,
    source_timestamp,
)


class GoogleEmailToGHunt(BaseTransform):
    name = "google_email_to_ghunt"
    display_name = "Google Email to GHunt"
    description = "Imports GHunt Google-account evidence into the graph from pasted JSON output"
    input_types = [EntityType.EMAIL_ADDRESS]
    output_types = [EntityType.SOCIAL_MEDIA, EntityType.IDENTIFIER, EntityType.DOCUMENT]
    category = "People"
    settings = [
        TransformSetting(
            name="result_json",
            display_name="GHunt JSON Output",
            description="JSON output captured from an external GHunt email run.",
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
            description="Optional GHunt version string.",
            default="",
            field_type="string",
        ),
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        email = entity.value.strip()
        timestamp = source_timestamp(config)
        payload, error = load_fixture_payload(config)
        command = f"ghunt email {email}"
        if error:
            return TransformResult(messages=[error, f"Run externally and paste JSON output: {command}"])
        if not isinstance(payload, dict):
            return TransformResult(messages=["GHunt fixture must be a JSON object."])

        warning = (
            "GHunt depends on Google-visible account signals and authenticated provider state; "
            "verify findings and respect applicable terms and consent boundaries."
        )
        profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
        gaia_id = self._gaia_id(payload, profile)
        profile_url = str(first_present(profile, ["profile_url", "url", "album_archive_url"], ""))
        account_name = str(first_present(profile, ["name", "full_name", "display_name"], ""))
        base_props = provenance_properties(
            tool_name="ghunt",
            command=command,
            source_timestamp=timestamp,
            tool_version=config.settings.get("tool_version", ""),
            confidence=0.9,
            raw_match_url=profile_url,
            warning=warning,
            raw_record=payload,
        )
        base_props.update({
            "email": email,
            "account_name": account_name,
            "gaia_id": gaia_id,
        })

        entities: list[Entity] = []
        edges: list[Edge] = []
        matches = 0

        if gaia_id:
            identifier = Entity(
                type=EntityType.IDENTIFIER,
                value=f"google-gaia:{gaia_id}",
                properties=base_props | {"identifier_type": "google_gaia_id"},
                source=self.name,
            )
            entities.append(identifier)
            edges.append(Edge(
                source_id=entity.id,
                target_id=identifier.id,
                label="has Google identifier",
                source_transform=self.name,
            ))
            matches += 1

        social = Entity(
            type=EntityType.SOCIAL_MEDIA,
            value=f"{email}@Google",
            properties=base_props | {"platform": "Google"},
            source=self.name,
        )
        entities.append(social)
        edges.append(Edge(
            source_id=entity.id,
            target_id=social.id,
            label="has Google account",
            source_transform=self.name,
        ))
        matches += 1

        doc = fixture_document(
            tool_name="GHunt",
            subject=email,
            match_count=matches,
            properties=base_props,
            source=self.name,
        )
        entities.append(doc)
        edges.append(Edge(source_id=entity.id, target_id=doc.id, label="tool evidence", source_transform=self.name))

        suffix = "entity" if matches == 1 else "entities"
        return TransformResult(entities=entities, edges=edges, messages=[f"GHunt fixture produced {matches} graph {suffix}."])

    @staticmethod
    def _gaia_id(payload: dict[str, Any], profile: dict[str, Any]) -> str:
        direct = first_present(
            payload,
            ["gaia_id", "gaiaId", "person_id", "personId", "google_id", "googleId"],
            "",
        )
        if direct:
            return str(direct)
        nested = first_present(
            profile,
            ["gaia_id", "gaiaId", "person_id", "personId", "google_id", "googleId"],
            "",
        )
        return str(nested)
