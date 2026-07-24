import asyncio
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
    long_description = (
        "First resolves the domain's MX records to check that mail delivery is "
        "plausible. If there are none, the domain does not exist, or the lookup "
        "errors, it stops there and returns an empty result with a message. When MX "
        "records are present their host names are listed in the result messages and "
        "the transform then generates a fixed set of six conventional role addresses "
        "at the domain: admin, info, postmaster, hostmaster, webmaster and abuse. "
        "Each becomes an EmailAddress entity carrying the prefix and domain as "
        "properties, linked from the domain with an 'email at' edge. The prefix list "
        "is hard-coded and identical for every domain; nothing is harvested from the "
        "target and no address is tested for delivery."
    )
    when_to_use = (
        "Use when you need plausible contact or abuse-reporting addresses for a "
        "domain and none have been collected yet, or as a quick check that a domain "
        "is set up to receive mail at all. Because the output is generated rather "
        "than observed, prefer URL to Content followed by Content to IOCs when the "
        "goal is addresses that genuinely exist, and use Domain to MX Records when "
        "you only care about the mail infrastructure itself."
    )
    limitations = (
        "Every address produced is a guess. None is verified by SMTP or any other "
        "check, so the entities assert only that the domain accepts mail, not that "
        "these mailboxes exist. The six prefixes are hard-coded, so the output is "
        "identical for every domain and carries no target-specific intelligence. "
        "Gating on MX means a domain that receives mail via an implicit A-record "
        "fallback produces nothing, and a resolver failure returns the same empty "
        "entity set as a domain with genuinely no mail, distinguishable only by the "
        "result message."
    )
    example_use_cases = [
        "Produce a likely abuse contact for reporting a malicious domain",
        "Confirm a domain is configured to receive mail before further email work",
        "Seed a graph with candidate role addresses for later verification",
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        domain = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        # Check if MX records exist for the domain
        try:
            mx_records = await asyncio.to_thread(dns.resolver.resolve, domain, "MX")
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
