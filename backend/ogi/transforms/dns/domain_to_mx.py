import asyncio
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
    long_description = (
        "Resolves the domain's MX (mail exchange) records and creates an MXRecord "
        "entity for each answer, using the mail host name with its trailing dot "
        "stripped as the entity value. The record's preference number is stored as a "
        "'priority' property and repeated in the edge label, so the graph shows at a "
        "glance which host is the primary exchanger and which are backups. The "
        "queried domain is also kept on each MXRecord as a property. Empty answers, "
        "non-existent domains and resolver errors are recorded as result messages "
        "rather than raised, so a failed lookup returns an empty result."
    )
    when_to_use = (
        "Use when you want to know who actually handles mail for a domain. An "
        "organisation running its own mail servers looks very different from one on "
        "a hosted provider, and the MX host names usually name the provider or "
        "filtering gateway outright. Take the mail host names forward as domains "
        "with Domain to IP Address to map the mail infrastructure, or run Domain to "
        "Email Addresses to build candidate addresses on the same domain."
    )
    limitations = (
        "MX records name the receiving host, not the mailbox provider behind it: "
        "many organisations point MX at a filtering gateway that relays onward to a "
        "different final destination. Only the current record set is visible, so a "
        "recent provider migration leaves no trace. An empty result does not prove "
        "the domain has no mail, since resolver failures and genuinely absent "
        "records both return no entities and differ only in the result message."
    )
    example_use_cases = [
        "Identify which mail provider or filtering gateway serves a target organisation",
        "Compare MX records across related domains to spot shared mail infrastructure",
        "Confirm a domain is configured to receive mail before attempting address work",
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        domain = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        try:
            answers = await asyncio.to_thread(dns.resolver.resolve, domain, "MX")
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
