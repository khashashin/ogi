import whois

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


class WhoisLookup(BaseTransform):
    name = "whois_lookup"
    display_name = "WHOIS Lookup"
    description = "Retrieves WHOIS registration data for a domain"
    input_types = [EntityType.DOMAIN]
    output_types = [EntityType.ORGANIZATION, EntityType.PERSON, EntityType.EMAIL_ADDRESS]
    category = "DNS"

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        domain = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        try:
            w = whois.whois(domain)

            # Registrar info
            if w.registrar:
                registrar_entity = Entity(
                    type=EntityType.ORGANIZATION,
                    value=str(w.registrar),
                    properties={"role": "registrar", "domain": domain},
                    source=self.name,
                )
                entities.append(registrar_entity)
                edges.append(Edge(
                    source_id=entity.id,
                    target_id=registrar_entity.id,
                    label="registered via",
                    source_transform=self.name,
                ))
                messages.append(f"Registrar: {w.registrar}")

            # Registrant org
            if w.org:
                org_entity = Entity(
                    type=EntityType.ORGANIZATION,
                    value=str(w.org),
                    properties={"role": "registrant", "domain": domain},
                    source=self.name,
                )
                entities.append(org_entity)
                edges.append(Edge(
                    source_id=entity.id,
                    target_id=org_entity.id,
                    label="registered to",
                    source_transform=self.name,
                ))
                messages.append(f"Organization: {w.org}")

            # Registrant name
            if w.name and isinstance(w.name, str):
                person_entity = Entity(
                    type=EntityType.PERSON,
                    value=w.name,
                    properties={"role": "registrant", "domain": domain},
                    source=self.name,
                )
                entities.append(person_entity)
                edges.append(Edge(
                    source_id=entity.id,
                    target_id=person_entity.id,
                    label="registrant",
                    source_transform=self.name,
                ))
                messages.append(f"Registrant: {w.name}")

            # Emails
            emails = w.emails if isinstance(w.emails, list) else ([w.emails] if w.emails else [])
            for email in emails:
                email_entity = Entity(
                    type=EntityType.EMAIL_ADDRESS,
                    value=str(email),
                    properties={"domain": domain, "source": "whois"},
                    source=self.name,
                )
                entities.append(email_entity)
                edges.append(Edge(
                    source_id=entity.id,
                    target_id=email_entity.id,
                    label="whois email",
                    source_transform=self.name,
                ))
                messages.append(f"Email: {email}")

            # Store WHOIS dates as properties on a copy of the input entity
            whois_props: dict[str, str] = {}
            if w.creation_date:
                date = w.creation_date[0] if isinstance(w.creation_date, list) else w.creation_date
                whois_props["whois_creation_date"] = str(date)
            if w.expiration_date:
                date = w.expiration_date[0] if isinstance(w.expiration_date, list) else w.expiration_date
                whois_props["whois_expiration_date"] = str(date)
            if w.updated_date:
                date = w.updated_date[0] if isinstance(w.updated_date, list) else w.updated_date
                whois_props["whois_updated_date"] = str(date)
            if w.dnssec:
                whois_props["dnssec"] = str(w.dnssec)
            if w.status:
                statuses = w.status if isinstance(w.status, list) else [w.status]
                whois_props["whois_status"] = ", ".join(str(s) for s in statuses)

            if whois_props:
                enriched = entity.model_copy(update={
                    "properties": {**entity.properties, **whois_props},
                })
                entities.append(enriched)
                for key, val in whois_props.items():
                    messages.append(f"{key}: {val}")

        except Exception as e:
            messages.append(f"WHOIS error: {e}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
