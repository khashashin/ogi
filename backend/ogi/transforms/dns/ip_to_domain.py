import asyncio
import dns.resolver
import dns.reversename

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


class IPToDomain(BaseTransform):
    name = "ip_to_domain"
    display_name = "IP to Domain (Reverse DNS)"
    description = "Performs reverse DNS lookup on an IP address"
    input_types = [EntityType.IP_ADDRESS]
    output_types = [EntityType.DOMAIN]
    category = "DNS"

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        ip_addr = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        try:
            rev_name = await asyncio.to_thread(dns.reversename.from_address, ip_addr)
            answers = await asyncio.to_thread(dns.resolver.resolve, rev_name, "PTR")
            for rdata in answers:
                domain = str(rdata.target).rstrip(".")
                domain_entity = Entity(
                    type=EntityType.DOMAIN,
                    value=domain,
                    properties={"source_ip": ip_addr},
                    source=self.name,
                )
                entities.append(domain_entity)
                edges.append(Edge(
                    source_id=entity.id,
                    target_id=domain_entity.id,
                    label="reverse DNS",
                    source_transform=self.name,
                ))
                messages.append(f"PTR: {domain}")
        except dns.resolver.NoAnswer:
            messages.append("No PTR records found")
        except dns.resolver.NXDOMAIN:
            messages.append("No reverse DNS entry")
        except Exception as e:
            messages.append(f"Error: {e}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
