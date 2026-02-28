import dns.resolver

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig

COMMON_PREFIXES = [
    "admin",
    "info",
    "postmaster",
    "hostmaster",
    "webmaster",
    "abuse",
]


class DomainToEmails(BaseTransform):
    name = "domain_to_emails"
    display_name = "Domain to Email Addresses"
    description = "Generates common email addresses for a domain after verifying MX records exist"
    input_types = [EntityType.DOMAIN]
    output_types = [EntityType.EMAIL_ADDRESS]
    category = "Email"

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        domain = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        # Check if MX records exist for the domain
        try:
            mx_records = dns.resolver.resolve(domain, "MX")
            mx_hosts = [str(rdata.exchange).rstrip(".") for rdata in mx_records]
            messages.append(f"MX records found: {', '.join(mx_hosts)}")
        except dns.resolver.NoAnswer:
            messages.append(f"No MX records found for {domain}")
            return TransformResult(entities=entities, edges=edges, messages=messages)
        except dns.resolver.NXDOMAIN:
            messages.append(f"Domain {domain} does not exist")
            return TransformResult(entities=entities, edges=edges, messages=messages)
        except Exception as e:
            messages.append(f"Error checking MX records: {e}")
            return TransformResult(entities=entities, edges=edges, messages=messages)

        # MX records exist, so email delivery is plausible
        for prefix in COMMON_PREFIXES:
            email_address = f"{prefix}@{domain}"
            email_entity = Entity(
                type=EntityType.EMAIL_ADDRESS,
                value=email_address,
                properties={"prefix": prefix, "domain": domain},
                source=self.name,
            )
            entities.append(email_entity)
            edges.append(Edge(
                source_id=entity.id,
                target_id=email_entity.id,
                label="email at",
                source_transform=self.name,
            ))
            messages.append(f"Generated: {email_address}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
