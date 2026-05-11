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
