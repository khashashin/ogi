import asyncio
import dns.resolver

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


class DomainToNS(BaseTransform):
    name = "domain_to_ns"
    display_name = "Domain to NS Records"
    description = "Looks up nameserver records for a domain"
    input_types = [EntityType.DOMAIN]
    output_types = [EntityType.NS_RECORD]
    category = "DNS"

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        domain = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        try:
            answers = await asyncio.to_thread(dns.resolver.resolve, domain, "NS")
            for rdata in answers:
                ns_host = str(rdata.target).rstrip(".")
                ns_entity = Entity(
                    type=EntityType.NS_RECORD,
                    value=ns_host,
                    properties={"domain": domain},
                    source=self.name,
                )
                entities.append(ns_entity)
                edges.append(Edge(
                    source_id=entity.id,
                    target_id=ns_entity.id,
                    label="nameserver",
                    source_transform=self.name,
                ))
                messages.append(f"NS: {ns_host}")
        except dns.resolver.NoAnswer:
            messages.append("No NS records found")
        except dns.resolver.NXDOMAIN:
            messages.append(f"Domain {domain} does not exist")
        except Exception as e:
            messages.append(f"Error: {e}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
