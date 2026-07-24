import asyncio
import dns.resolver

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


class DomainToIP(BaseTransform):
    name = "domain_to_ip"
    display_name = "Domain to IP Address"
    description = "Resolves A and AAAA records for a domain"
    input_types = [EntityType.DOMAIN]
    output_types = [EntityType.IP_ADDRESS]
    category = "DNS"
    long_description = (
        "Performs a DNS lookup of the domain's A (IPv4) and AAAA (IPv6) records "
        "and creates an IPAddress entity for each answer, linked back to the "
        "domain with a 'resolves to' edge that records which record type "
        "produced it. Results reflect what the resolver returns at this moment, "
        "so a domain behind a CDN or load balancer may return different "
        "addresses on each run."
    )
    when_to_use = (
        "Use this as the first step when pivoting from a domain to the "
        "infrastructure hosting it. Once you have the IP addresses you can "
        "continue with IP to ASN, IP to Geolocation, or reverse DNS to find "
        "other domains on the same host."
    )
    limitations = (
        "Returns only current DNS answers, not historical ones. Domains fronted "
        "by a CDN resolve to the CDN's edge nodes rather than the origin server, "
        "so shared-hosting conclusions drawn from these addresses can be "
        "misleading."
    )
    example_use_cases = [
        "Map a target domain to its hosting infrastructure before scanning",
        "Check whether several domains in an investigation share an IP address",
        "Establish a starting point for ASN and geolocation enrichment",
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        domain = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        for rdtype in ["A", "AAAA"]:
            try:
                answers = await asyncio.to_thread(dns.resolver.resolve, domain, rdtype)
                for rdata in answers:
                    ip_str = str(rdata)
                    ip_entity = Entity(
                        type=EntityType.IP_ADDRESS,
                        value=ip_str,
                        properties={"record_type": rdtype},
                        source=self.name,
                    )
                    entities.append(ip_entity)
                    edges.append(Edge(
                        source_id=entity.id,
                        target_id=ip_entity.id,
                        label=f"resolves to ({rdtype})",
                        source_transform=self.name,
                    ))
                    messages.append(f"{rdtype}: {ip_str}")
            except dns.resolver.NoAnswer:
                messages.append(f"No {rdtype} records found")
            except dns.resolver.NXDOMAIN:
                messages.append(f"Domain {domain} does not exist")
                break
            except Exception as e:
                messages.append(f"Error resolving {rdtype}: {e}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
