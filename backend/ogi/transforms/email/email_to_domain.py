from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


class EmailToDomain(BaseTransform):
    name = "email_to_domain"
    display_name = "Email to Domain"
    description = "Extracts the domain from an email address"
    input_types = [EntityType.EMAIL_ADDRESS]
    output_types = [EntityType.DOMAIN]
    category = "Email"

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
