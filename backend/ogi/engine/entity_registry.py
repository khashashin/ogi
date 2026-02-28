from ogi.models.entity import EntityType, ENTITY_TYPE_META


class EntityTypeInfo:
    def __init__(self, entity_type: EntityType, icon: str, color: str, category: str) -> None:
        self.entity_type = entity_type
        self.icon = icon
        self.color = color
        self.category = category

    def to_dict(self) -> dict[str, str]:
        return {
            "type": self.entity_type.value,
            "icon": self.icon,
            "color": self.color,
            "category": self.category,
        }


class EntityRegistry:
    _instance: "EntityRegistry | None" = None

    def __init__(self) -> None:
        self._types: dict[str, EntityTypeInfo] = {}
        self._register_builtins()

    @classmethod
    def instance(cls) -> "EntityRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _register_builtins(self) -> None:
        for entity_type, meta in ENTITY_TYPE_META.items():
            self.register_type(
                entity_type,
                icon=meta["icon"],
                color=meta["color"],
                category=meta["category"],
            )

    def register_type(
        self,
        entity_type: EntityType,
        icon: str,
        color: str,
        category: str,
    ) -> None:
        self._types[entity_type.value] = EntityTypeInfo(
            entity_type=entity_type,
            icon=icon,
            color=color,
            category=category,
        )

    def get_type(self, name: str) -> EntityTypeInfo | None:
        return self._types.get(name)

    def list_types(self) -> list[EntityTypeInfo]:
        return list(self._types.values())

    def list_types_dict(self) -> list[dict[str, str]]:
        return [t.to_dict() for t in self._types.values()]
