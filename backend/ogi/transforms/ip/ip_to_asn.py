import asyncio
import dns.resolver

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


class IPToASN(BaseTransform):
    name = "ip_to_asn"
    display_name = "IP to ASN"
    description = "Looks up ASN and organization for an IP address via DNS query to Team Cymru"
    input_types = [EntityType.IP_ADDRESS]
    output_types = [EntityType.AS_NUMBER, EntityType.ORGANIZATION]
    category = "IP Intelligence"
    long_description = (
        "Performs Team Cymru's DNS-based IP-to-ASN lookup. The IPv4 address is reversed and "
        "queried as a TXT record under origin.asn.cymru.com, which returns the announcing AS "
        "number together with the covering prefix, country, registry and allocation date. Only "
        "the first TXT answer is used. An ASNumber entity is created from it, carrying those "
        "fields as properties and linked to the IP with a 'belongs to ASN' edge. The transform "
        "then queries AS<number>.asn.cymru.com for the AS name and, when one comes back, "
        "creates an Organization entity holding the ASN, country and registry, linked to the IP "
        "with an 'operated by' edge. Everything runs over ordinary DNS resolution, so no API "
        "key or account is required."
    )
    when_to_use = (
        "Use it to establish which network actually announces an address, the most dependable "
        "ownership signal available for infrastructure. Run it on addresses produced by Domain "
        "to IP when you need to tell a target's own network apart from shared hosting or cloud "
        "ranges, and pair it with IP to Geolocation for a physical estimate. The Organization "
        "entity is a useful pivot for grouping unrelated-looking addresses under one operator."
    )
    limitations = (
        "IPv4 only: the input is split on dots and anything that is not four octets is "
        "rejected, so IPv6 addresses yield nothing. Only the first TXT answer is processed, so "
        "an address covered by more than one announcement shows a single ASN. The AS holder is "
        "the network announcing the prefix, not necessarily the party using the address, so "
        "cloud, CDN and hosting ranges name the provider rather than the tenant. Registry data "
        "lags reassignments, and the lookup depends on Team Cymru's DNS service being reachable "
        "from the resolver in use."
    )
    example_use_cases = [
        "Determine whether a set of IP addresses belongs to one operator or several",
        "Attribute a suspicious address to a hosting provider or abuse-tolerant network",
        "Separate a target's own netblock from generic cloud infrastructure",
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        ip = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        try:
            octets = ip.split(".")
            if len(octets) != 4:
                messages.append(f"Invalid IPv4 address: {ip}")
                return TransformResult(entities=entities, edges=edges, messages=messages)

            reversed_octets = ".".join(reversed(octets))
            query_name = f"{reversed_octets}.origin.asn.cymru.com"

            answers = await asyncio.to_thread(dns.resolver.resolve, query_name, "TXT")

            for rdata in answers:
                txt = str(rdata).strip('"')
                # Format: "AS_NUMBER | prefix | country | registry | allocated"
                parts = [p.strip() for p in txt.split("|")]
                if len(parts) < 5:
                    messages.append(f"Unexpected TXT record format: {txt}")
                    continue

                as_number = parts[0]
                prefix = parts[1]
                country = parts[2]
                registry = parts[3]
                allocated = parts[4]

                as_value = f"AS{as_number}" if not as_number.upper().startswith("AS") else as_number
                as_entity = Entity(
                    type=EntityType.AS_NUMBER,
                    value=as_value,
                    properties={
                        "prefix": prefix,
                        "country": country,
                        "registry": registry,
                        "allocated": allocated,
                    },
                    source=self.name,
                )
                entities.append(as_entity)
                edges.append(Edge(
                    source_id=entity.id,
                    target_id=as_entity.id,
                    label="belongs to ASN",
                    source_transform=self.name,
                ))
                messages.append(f"ASN: {as_value} (prefix: {prefix}, country: {country})")

                # Look up the ASN name for the organization
                try:
                    asn_query = f"AS{as_number}.asn.cymru.com"
                    asn_answers = await asyncio.to_thread(dns.resolver.resolve, asn_query, "TXT")
                    for asn_rdata in asn_answers:
                        asn_txt = str(asn_rdata).strip('"')
                        # Format: "AS_NUMBER | country | registry | allocated | org_name"
                        asn_parts = [p.strip() for p in asn_txt.split("|")]
                        if len(asn_parts) >= 5:
                            org_name = asn_parts[4]
                            if org_name:
                                org_entity = Entity(
                                    type=EntityType.ORGANIZATION,
                                    value=org_name,
                                    properties={
                                        "asn": as_value,
                                        "country": country,
                                        "registry": registry,
                                    },
                                    source=self.name,
                                )
                                entities.append(org_entity)
                                edges.append(Edge(
                                    source_id=entity.id,
                                    target_id=org_entity.id,
                                    label="operated by",
                                    source_transform=self.name,
                                ))
                                messages.append(f"Organization: {org_name}")
                except Exception as e:
                    messages.append(f"Error looking up ASN name: {e}")

                # Only process the first TXT record
                break

        except dns.resolver.NoAnswer:
            messages.append(f"No ASN information found for {ip}")
        except dns.resolver.NXDOMAIN:
            messages.append(f"No ASN record exists for {ip}")
        except dns.resolver.NoNameservers:
            messages.append(f"DNS servers unavailable for ASN lookup of {ip}")
        except Exception as e:
            messages.append(f"Error during ASN lookup: {e}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
