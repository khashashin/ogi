from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from ogi.config import settings
from ogi.models import Entity, EntityType, TransformResult


class TransformSetting(BaseModel):
    name: str
    display_name: str
    description: str = ""
    required: bool = False
    default: str = ""
    field_type: str = "string"  # string | integer | number | boolean | select | secret
    options: list[str] = Field(default_factory=list)
    min_value: float | None = None
    max_value: float | None = None
    pattern: str = ""


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

    @classmethod
    def effective_max_value(cls, setting_name: str, declared_max: float | None) -> float | None:
        overrides = getattr(settings, "transform_setting_max_overrides", {}) or {}
        override = overrides.get(setting_name)
        if setting_name in overrides:
            return override
        return declared_max

    @classmethod
    def effective_setting(cls, setting: TransformSetting) -> TransformSetting:
        effective = setting.model_copy()
        effective.max_value = cls.effective_max_value(setting.name, setting.max_value)
        return effective

    @classmethod
    def effective_settings(cls) -> list[TransformSetting]:
        return [cls.effective_setting(setting) for setting in getattr(cls, "settings", [])]

    @classmethod
    def get_effective_setting_max(cls, setting_name: str, declared_max: float | None) -> float | None:
        return cls.effective_max_value(setting_name, declared_max)

    @classmethod
    def parse_int_setting(
        cls,
        raw: str | None,
        *,
        setting_name: str,
        default: int,
        min_value: int | None = None,
        declared_max: int | None = None,
    ) -> int:
        try:
            parsed = int(str(raw).strip()) if raw is not None else default
        except Exception:
            parsed = default

        if min_value is not None and parsed < min_value:
            parsed = min_value

        effective_max = cls.get_effective_setting_max(setting_name, declared_max)
        if effective_max is not None and parsed > int(effective_max):
            parsed = int(effective_max)

        return parsed

    @classmethod
    def parse_float_setting(
        cls,
        raw: str | None,
        *,
        setting_name: str,
        default: float,
        min_value: float | None = None,
        declared_max: float | None = None,
    ) -> float:
        try:
            parsed = float(str(raw).strip()) if raw is not None else default
        except Exception:
            parsed = default

        if min_value is not None and parsed < min_value:
            parsed = min_value

        effective_max = cls.get_effective_setting_max(setting_name, declared_max)
        if effective_max is not None and parsed > effective_max:
            parsed = effective_max

        return parsed
