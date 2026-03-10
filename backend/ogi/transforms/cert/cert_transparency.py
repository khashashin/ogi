import httpx

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


class CertTransparency(BaseTransform):
    name = "cert_transparency"
    display_name = "Certificate Transparency Lookup"
    description = "Discovers subdomains via Certificate Transparency logs (crt.sh)"
    input_types = [EntityType.DOMAIN]
    output_types = [EntityType.SUBDOMAIN]
    category = "Certificate"

    async def run(self, entity: Entity, _config: TransformConfig) -> TransformResult:
        domain = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []
        max_results = self.get_effective_setting_max("max_results", 500)

        url = f"https://crt.sh/?q=%25.{domain}&output=json"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()

            records: list[dict[str, str | int]] = response.json()

            # Collect unique subdomain values
            seen: set[str] = set()
            for record in records:
                common_name = str(record.get("common_name", "")).strip().lower()

                # Skip empty, wildcard, and non-subdomain entries
                if not common_name:
                    continue
                if common_name.startswith("*"):
                    continue
                if not common_name.endswith(f".{domain.lower()}"):
                    continue
                # Skip if it is the domain itself
                if common_name == domain.lower():
                    continue

                seen.add(common_name)

            if max_results is not None and len(seen) > int(max_results):
                messages.append(
                    f"Found {len(seen)} subdomains, limiting to {int(max_results)}. "
                    "Consider narrowing your search or rate limiting may apply."
                )

            for subdomain_value in sorted(seen)[: int(max_results) if max_results is not None else None]:
                subdomain_entity = Entity(
                    type=EntityType.SUBDOMAIN,
                    value=subdomain_value,
                    properties={"parent_domain": domain, "source": "crt.sh"},
                    source=self.name,
                )
                entities.append(subdomain_entity)
                edges.append(Edge(
                    source_id=subdomain_entity.id,
                    target_id=entity.id,
                    label="subdomain of",
                    source_transform=self.name,
                ))

            messages.append(f"Found {len(entities)} unique subdomains via crt.sh")

        except httpx.TimeoutException:
            messages.append(f"Request to crt.sh timed out for {domain}")
        except httpx.HTTPStatusError as e:
            messages.append(f"crt.sh returned HTTP {e.response.status_code} for {domain}")
        except Exception as e:
            messages.append(f"Error querying crt.sh for {domain}: {e}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
