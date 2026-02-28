import dns.resolver

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


class DomainToMX(BaseTransform):
    name = "domain_to_mx"
    display_name = "Domain to MX Records"
    description = "Looks up MX (mail exchange) records for a domain"
    input_types = [EntityType.DOMAIN]
    output_types = [EntityType.MX_RECORD]
    category = "DNS"

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        domain = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        try:
            answers = dns.resolver.resolve(domain, "MX")
            for rdata in answers:
                mx_host = str(rdata.exchange).rstrip(".")
                priority = rdata.preference
                mx_entity = Entity(
                    type=EntityType.MX_RECORD,
                    value=mx_host,
                    properties={"priority": priority, "domain": domain},
                    source=self.name,
                )
                entities.append(mx_entity)
                edges.append(Edge(
                    source_id=entity.id,
                    target_id=mx_entity.id,
                    label=f"MX (pri={priority})",
                    source_transform=self.name,
                ))
                messages.append(f"MX: {mx_host} (priority {priority})")
        except dns.resolver.NoAnswer:
            messages.append("No MX records found")
        except dns.resolver.NXDOMAIN:
            messages.append(f"Domain {domain} does not exist")
        except Exception as e:
            messages.append(f"Error: {e}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
