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

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        domain = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        for rdtype in ["A", "AAAA"]:
            try:
                answers = dns.resolver.resolve(domain, rdtype)
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
