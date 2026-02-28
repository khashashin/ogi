from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from ogi.models import Entity, EntityType, TransformResult


class TransformSetting(BaseModel):
    name: str
    display_name: str
    description: str = ""
    required: bool = False
    default: str = ""


class TransformConfig(BaseModel):
    settings: dict[str, str] = Field(default_factory=dict)


class BaseTransform(ABC):
    name: str = ""
    display_name: str = ""
    description: str = ""
    input_types: list[EntityType] = []
    output_types: list[EntityType] = []
    category: str = "General"
    settings: list[TransformSetting] = []

    @abstractmethod
    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        ...

    def can_run_on(self, entity: Entity) -> bool:
        return entity.type in self.input_types
