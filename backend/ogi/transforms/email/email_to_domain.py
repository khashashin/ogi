from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


class EmailToDomain(BaseTransform):
    name = "email_to_domain"
    display_name = "Email to Domain"
    description = "Extracts the domain from an email address"
    input_types = [EntityType.EMAIL_ADDRESS]
    output_types = [EntityType.DOMAIN]
    category = "Email"
    long_description = (
        "Splits the email address on its first '@' and takes everything after it as "
        "the domain, trimming surrounding whitespace and lowercasing the result. "
        "That value becomes a Domain entity carrying the original address in an "
        "'extracted_from' property, linked from the email address with an 'email "
        "hosted at' edge. The work is purely local string handling: no DNS query or "
        "network call is made, so it costs nothing and always succeeds for a "
        "well-formed address. An address with no '@', or with nothing after it, "
        "produces an empty result and an explanatory message."
    )
    when_to_use = (
        "Use to turn a collected address into a pivot point so that domain-level "
        "transforms become available on it. This is the usual bridge between the "
        "people-centred and infrastructure-centred halves of an investigation: "
        "follow it with WHOIS Lookup for registration detail, Domain to MX Records "
        "to see who handles the mail, or Domain to IP Address to reach the hosting."
    )
    limitations = (
        "The domain is taken from the address text alone and never validated, so "
        "typos, disposable domains and spoofed sender addresses all produce a Domain "
        "entity indistinguishable from a real one. Free webmail addresses yield a "
        "shared consumer domain that says nothing about the individual and will pull "
        "unrelated entities together if several such addresses are expanded onto one "
        "graph. Splitting always happens at the first '@', so a quoted local part "
        "containing an '@' is cut at the wrong point."
    )
    example_use_cases = [
        "Pivot from a breach-derived address to the organisation's domain and hosting",
        "Group a list of collected contact addresses by employer domain",
        "Bridge a person-centred subgraph into the DNS and WHOIS transforms",
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        email = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        if "@" not in email:
            messages.append(f"Invalid email address: {email}")
            return TransformResult(entities=entities, edges=edges, messages=messages)

        domain = email.split("@", 1)[1].strip().lower()

        if not domain:
            messages.append(f"Could not extract domain from: {email}")
            return TransformResult(entities=entities, edges=edges, messages=messages)

        domain_entity = Entity(
            type=EntityType.DOMAIN,
            value=domain,
            properties={"extracted_from": email},
            source=self.name,
        )
        entities.append(domain_entity)
        edges.append(Edge(
            source_id=entity.id,
            target_id=domain_entity.id,
            label="email hosted at",
            source_transform=self.name,
        ))
        messages.append(f"Extracted domain: {domain}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
