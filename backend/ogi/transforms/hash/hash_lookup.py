import httpx

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig, TransformSetting


class HashLookup(BaseTransform):
    name = "hash_lookup"
    display_name = "Hash Lookup"
    description = "Looks up a file hash on VirusTotal for threat intelligence"
    input_types = [EntityType.HASH]
    output_types = [EntityType.HASH]
    category = "Hash"
    settings = [
        TransformSetting(
            name="virustotal_api_key",
            display_name="VirusTotal API Key",
            description="API key for VirusTotal lookups",
            required=True,
            field_type="secret",
        ),
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        hash_value = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        api_key = config.settings.get("virustotal_api_key", "")
        if not api_key:
            messages.append(
                "VirusTotal API key required. Configure in transform settings."
            )
            return TransformResult(entities=entities, edges=edges, messages=messages)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://www.virustotal.com/api/v3/files/{hash_value}",
                    headers={"x-apikey": api_key},
                )
                response.raise_for_status()
                data = response.json()

            attributes = data.get("data", {}).get("attributes", {})
            analysis_stats = attributes.get("last_analysis_stats", {})

            malicious = analysis_stats.get("malicious", 0)
            total_engines = sum(analysis_stats.values()) if analysis_stats else 0
            detection_ratio = f"{malicious}/{total_engines}"

            file_type = attributes.get("type_description", "")
            file_size = attributes.get("size", 0)
            first_seen = attributes.get("first_submission_date", "")
            last_seen = attributes.get("last_analysis_date", "")

            enriched_properties: dict[str, str | int | float | bool | None] = {
                **entity.properties,
                "detection_ratio": detection_ratio,
                "file_type": file_type,
                "file_size": file_size,
                "first_seen": str(first_seen) if first_seen else "",
                "last_seen": str(last_seen) if last_seen else "",
            }

            enriched = entity.model_copy(update={
                "properties": enriched_properties,
            })
            entities.append(enriched)

            messages.append(f"Detection ratio: {detection_ratio}")
            if file_type:
                messages.append(f"File type: {file_type}")
            if file_size:
                messages.append(f"File size: {file_size} bytes")
            if first_seen:
                messages.append(f"First seen: {first_seen}")
            if last_seen:
                messages.append(f"Last seen: {last_seen}")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                messages.append(f"Hash {hash_value} not found on VirusTotal")
            elif e.response.status_code == 401:
                messages.append("Invalid VirusTotal API key")
            elif e.response.status_code == 429:
                messages.append("VirusTotal API rate limit exceeded")
            else:
                messages.append(f"VirusTotal HTTP error: {e}")
        except httpx.RequestError as e:
            messages.append(f"Request error contacting VirusTotal: {e}")
        except Exception as e:
            messages.append(f"Error during hash lookup: {e}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
