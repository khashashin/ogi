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
    long_description = (
        "Resolves the domain's NS records and creates an NSRecord entity for every "
        "nameserver returned, stripping the trailing dot from the host name and "
        "storing the queried domain as a property. Each nameserver is linked back to "
        "the domain with a plain 'nameserver' edge. The answer reflects the "
        "delegation as the configured resolver sees it right now. Empty answers, "
        "non-existent domains and resolver errors are reported as result messages "
        "and return an empty result rather than raising."
    )
    when_to_use = (
        "Use when you want to know who runs DNS for a domain. Nameserver names "
        "normally identify the registrar, hosting provider or managed DNS service, "
        "and an unusual or self-hosted nameserver set is a strong way to cluster "
        "domains belonging to the same operator. Follow with Domain to IP Address "
        "against the nameserver host names to reach the servers themselves, or "
        "WHOIS Lookup for registrar and registration detail."
    )
    limitations = (
        "Nameservers identify the DNS provider, not the domain owner. Registrar "
        "default and CDN nameservers are shared by millions of unrelated domains, so "
        "a shared nameserver is weak evidence of a relationship unless the "
        "nameserver is itself unusual. Only the current delegation is returned, with "
        "no history of previous providers, and the transform reads the resolver's "
        "answer rather than querying the parent zone, so it does not reveal "
        "mismatches between parent glue and the zone's own NS set."
    )
    example_use_cases = [
        "Identify the DNS provider or registrar standing behind a target domain",
        "Cluster investigation domains that share an unusual, non-default nameserver set",
        "Check whether a domain uses a privacy-oriented or bulletproof DNS operator",
    ]

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
