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
    long_description = (
        "Queries the public crt.sh Certificate Transparency database with a wildcard "
        "search for certificates issued under the domain, then turns the answers "
        "into Subdomain entities. Each JSON record's common_name field is lowercased "
        "and kept only if it is a strict child of the queried domain; blanks, "
        "wildcard entries and the domain itself are discarded, and what remains is "
        "deduplicated and sorted. Every surviving name becomes a Subdomain entity "
        "carrying the parent domain and a source of 'crt.sh', joined to the domain "
        "by a 'subdomain of' edge pointing from the subdomain up to the parent. The "
        "number of entities is capped by the max_results setting, which defaults to "
        "500, and a message reports the true count whenever the cap truncates the "
        "list. The HTTP request has a thirty second timeout; timeouts, HTTP error "
        "statuses and parse failures are reported as messages with an empty result."
    )
    when_to_use = (
        "Use early when scoping a target's attack surface. Certificate Transparency "
        "is entirely passive, requires no contact with the target, and routinely "
        "exposes internal-sounding hosts such as staging, vpn and mail gateways that "
        "never appear in public links. Feed the discovered names into Domain to IP "
        "Address to see which still resolve, then use Domain to SSL Certificates or "
        "IP to ASN on the ones that look interesting."
    )
    limitations = (
        "Only the common_name field of each record is read, so names that appear "
        "solely in a certificate's subject alternative names are missed, which can "
        "be a large share of results for multi-domain certificates. Wildcard entries "
        "are dropped rather than expanded. CT logs record issuance, not deployment: "
        "many returned hosts expired long ago or never went live, so each name needs "
        "a resolution check before use. crt.sh is a free service that is frequently "
        "slow or briefly unavailable, and a timeout returns an empty result with a "
        "message rather than an error."
    )
    example_use_cases = [
        "Enumerate a target's subdomains passively before any active scanning",
        "Surface staging, admin and VPN hosts that are not linked from the public site",
        "Compare subdomain lists for two organisations suspected of sharing infrastructure",
    ]

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
