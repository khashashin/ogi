"""Example plugin transform that echoes the input entity."""
from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


class HelloWorldTransform(BaseTransform):
    name = "hello_world"
    display_name = "Hello World"
    description = "Example plugin transform — creates a note entity linked to the input"
    input_types = [EntityType.DOMAIN, EntityType.IP_ADDRESS, EntityType.PERSON]
    output_types = [EntityType.DOCUMENT]
    category = "Example"

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        note = Entity(
            type=EntityType.DOCUMENT,
            value=f"Hello from plugin! Input: {entity.value}",
            properties={"source_type": entity.type.value, "source_value": entity.value},
            source="example-plugin",
        )
        edge = Edge(
            source_id=entity.id,
            target_id=note.id,
            label="hello_world",
            source_transform="hello_world",
        )
        return TransformResult(
            entities=[note],
            edges=[edge],
            messages=[f"Created note for {entity.value}"],
        )
