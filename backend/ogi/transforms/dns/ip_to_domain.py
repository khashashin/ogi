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
    long_description = (
        "Builds the reverse lookup name for the address (in-addr.arpa for IPv4, "
        "ip6.arpa for IPv6) and resolves its PTR records. Each name returned becomes "
        "a Domain entity carrying the originating address in a 'source_ip' property, "
        "linked from the IP address with a 'reverse DNS' edge. Most addresses "
        "publish at most one PTR record, so this usually yields a single host name. "
        "Missing PTR records, absent reverse delegation and resolver errors are "
        "reported as result messages and return an empty result."
    )
    when_to_use = (
        "Use to put a name to a bare IP address. Provider PTR naming conventions "
        "often reveal the hosting company, the data centre and occasionally the "
        "customer, even for addresses with no other obvious attribution. Pair it "
        "with Domain to IP Address to check the name resolves back to the same "
        "address, and follow with IP to ASN or IP to Geolocation for ownership and "
        "location context."
    )
    limitations = (
        "PTR records are published by whoever controls the address block, not by the "
        "domain owner, so the name returned is unverified and can be set to anything; "
        "always confirm it with a forward lookup before treating it as ownership "
        "evidence. This is not a way to enumerate the sites hosted on an address: a "
        "shared web host serving thousands of domains typically has one generic PTR "
        "name. Many cloud, mobile and residential addresses have no PTR record at "
        "all, which returns an empty result."
    )
    example_use_cases = [
        "Identify the hosting provider or data centre behind an unattributed IP address",
        "Confirm forward and reverse DNS agree before trusting a host name",
        "Give readable labels to IP addresses collected during infrastructure mapping",
    ]

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
