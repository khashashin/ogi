from __future__ import annotations

from typing import Any
from uuid import UUID
from uuid import UUID as UUIDType

from fastapi import HTTPException

from ogi.agent.tools import ToolContext, ToolDefinition, ToolRegistry, ToolResult
from ogi.engine.plugin_engine import PluginEngine
from ogi.engine.transform_engine import TransformEngine
from ogi.engine.transform_execution_service import TransformExecutionService
from ogi.models import TransformInfo
from ogi.models import EntityType
from ogi.store.entity_store import EntityStore
from ogi.store.transform_run_store import TransformRunStore


def _parse_entity_type(value: str | None) -> EntityType | None:
    if not value:
        return None
    return EntityType(value)


def _enrich_transform_info_local(transform: TransformInfo, plugin_engine: PluginEngine) -> TransformInfo:
    plugin_name = plugin_engine.get_plugin_for_transform(transform.name)
    if plugin_name is None:
        return transform

    plugin = plugin_engine.get_plugin(plugin_name)
    if plugin is None:
        return transform.model_copy(update={"plugin_name": plugin_name})

    return transform.model_copy(
        update={
            "plugin_name": plugin_name,
            "plugin_verification_tier": plugin.verification_tier or "community",
            "plugin_permissions": plugin.permissions or {},
            "plugin_source": plugin.source or "local",
        }
    )


def _ensure_scope(ctx: ToolContext, entity_id: UUID) -> None:
    if ctx.scope.mode == "selected" and entity_id not in set(ctx.scope.entity_ids):
        raise HTTPException(status_code=400, detail="Entity is outside the allowed investigation scope")


def _try_parse_uuid(value: object) -> UUID | None:
    try:
        return UUIDType(str(value))
    except (TypeError, ValueError):
        return None


async def _resolve_entity(ctx: ToolContext, params: dict[str, Any]) -> tuple[UUID, Any]:
    store = EntityStore(ctx.session)

    entity_id = _try_parse_uuid(params.get("entity_id"))
    if entity_id is not None:
        _ensure_scope(ctx, entity_id)
        entity = await store.get(entity_id)
        if entity is None or entity.project_id != ctx.project_id:
            raise HTTPException(status_code=404, detail="Entity not found")
        return entity_id, entity

    entity_value = str(params.get("entity_value") or params.get("entity_id") or "").strip()
    if not entity_value:
        raise HTTPException(status_code=400, detail="entity_id or entity_value is required")

    matches = await store.search(ctx.project_id, entity_value, limit=25)
    exact_matches = [entity for entity in matches if entity.value == entity_value]
    if ctx.scope.mode == "selected":
        allowed = set(ctx.scope.entity_ids)
        exact_matches = [entity for entity in exact_matches if entity.id in allowed]

    if not exact_matches:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_value}' not found in the investigation scope")
    if len(exact_matches) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Entity value '{entity_value}' matched multiple entities. "
                "Use entity_id from list_entities or get_entity."
            ),
        )
    entity = exact_matches[0]
    return entity.id, entity


def build_default_tool_registry(
    *,
    transform_engine: TransformEngine,
    plugin_engine: PluginEngine,
    transform_execution_service: TransformExecutionService,
) -> ToolRegistry:
    registry = ToolRegistry()

    async def list_entities(params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        store = EntityStore(ctx.session)
        type_filter = _parse_entity_type(params.get("type_filter"))
        limit = int(params.get("limit", 25))
        entities = await store.list_by_project(ctx.project_id, type_filter=type_filter, limit=limit)
        if ctx.scope.mode == "selected":
            allowed = set(ctx.scope.entity_ids)
            entities = [entity for entity in entities if entity.id in allowed]
        payload = [
            {
                "id": str(entity.id),
                "type": entity.type.value,
                "value": entity.value,
                "tags": entity.tags,
            }
            for entity in entities
        ]
        return ToolResult(
            data={"entities": payload},
            summary=f"Listed {len(payload)} entities from the project scope.",
        )

    async def get_entity(params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        _entity_id, entity = await _resolve_entity(ctx, params)
        return ToolResult(
            data={
                "entity": {
                    "id": str(entity.id),
                    "type": entity.type.value,
                    "value": entity.value,
                    "properties": entity.properties,
                    "notes": entity.notes,
                    "tags": entity.tags,
                }
            },
            summary=f"Loaded entity {entity.value} ({entity.type.value}).",
        )

    async def search_graph(params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        query = str(params.get("query", "")).strip()
        if not query:
            raise HTTPException(status_code=400, detail="query is required")
        store = EntityStore(ctx.session)
        type_filter = _parse_entity_type(params.get("type_filter"))
        limit = int(params.get("limit", 25))
        entities = await store.search(ctx.project_id, query, type_filter=type_filter, limit=limit)
        if ctx.scope.mode == "selected":
            allowed = set(ctx.scope.entity_ids)
            entities = [entity for entity in entities if entity.id in allowed]
        return ToolResult(
            data={
                "entities": [
                    {
                        "id": str(entity.id),
                        "type": entity.type.value,
                        "value": entity.value,
                    }
                    for entity in entities
                ]
            },
            summary=f"Search for '{query}' returned {len(entities)} matching entities.",
        )

    async def list_transforms(params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        _entity_id, entity = await _resolve_entity(ctx, params)
        transforms = [
            _enrich_transform_info_local(item, plugin_engine)
            for item in transform_engine.list_for_entity(entity)
        ]
        return ToolResult(
            data={
                "transforms": [
                    {
                        "name": item.name,
                        "display_name": item.display_name,
                        "description": item.description,
                        "category": item.category,
                        "api_key_services": item.api_key_services,
                        "plugin_name": item.plugin_name,
                        "plugin_verification_tier": item.plugin_verification_tier,
                    }
                    for item in transforms
                ]
            },
            summary=f"Found {len(transforms)} runnable transforms for {entity.value}.",
        )

    async def run_transform(params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        entity_id, _entity = await _resolve_entity(ctx, params)
        transform_name = str(params["transform_name"])
        overrides = params.get("config", {})
        if not isinstance(overrides, dict):
            raise HTTPException(status_code=400, detail="config must be an object")
        prepared = await transform_execution_service.validate_and_prepare(
            transform_name=transform_name,
            entity_id=entity_id,
            project_id=ctx.project_id,
            user_id=ctx.user_id,
            config_overrides={str(key): str(value) for key, value in overrides.items()},
            session=ctx.session,
        )
        run, result = await transform_execution_service.execute_direct(prepared=prepared, session=ctx.session)
        return ToolResult(
            data={
                "transform_run": {
                    "id": str(run.id),
                    "status": run.status.value,
                    "transform_name": run.transform_name,
                    "input_entity_id": str(run.input_entity_id),
                },
                "result": result,
            },
            summary=(
                f"Ran transform {transform_name} on entity {entity_id} and produced "
                f"{len(result.get('entities', []))} entities and {len(result.get('edges', []))} edges."
            ),
        )

    async def get_transform_result(params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        run_id = UUID(str(params["run_id"]))
        store = TransformRunStore(ctx.session)
        run = await store.get(run_id)
        if run is None or run.project_id != ctx.project_id:
            raise HTTPException(status_code=404, detail="Transform run not found")
        return ToolResult(
            data={
                "transform_run": {
                    "id": str(run.id),
                    "status": run.status.value,
                    "transform_name": run.transform_name,
                    "input_entity_id": str(run.input_entity_id),
                    "result": run.result,
                    "error": run.error,
                }
            },
            summary=f"Loaded transform run {run.id} with status {run.status.value}.",
        )

    async def finish_investigation(params: dict[str, Any], _ctx: ToolContext) -> ToolResult:
        summary = str(params.get("summary", "")).strip()
        return ToolResult(
            data={"summary": summary},
            summary=summary or "Finished the investigation.",
        )

    registry.register(
        ToolDefinition(
            name="list_entities",
            description="List entities in the current investigation scope.",
            parameters={
                "type": "object",
                "properties": {
                    "type_filter": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "additionalProperties": False,
            },
            risk_level="low",
            requires_approval=False,
        ),
        list_entities,
    )
    registry.register(
        ToolDefinition(
            name="get_entity",
            description="Load one entity with its notes, tags, and properties. Prefer entity_id from list_entities, but exact entity_value is also accepted.",
            parameters={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "entity_value": {"type": "string"},
                },
                "additionalProperties": False,
            },
            risk_level="low",
            requires_approval=False,
        ),
        get_entity,
    )
    registry.register(
        ToolDefinition(
            name="search_graph",
            description="Search entity values inside the current project scope.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "type_filter": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            risk_level="low",
            requires_approval=False,
        ),
        search_graph,
    )
    registry.register(
        ToolDefinition(
            name="list_transforms",
            description="List transforms that can run on a specific entity. Prefer entity_id from list_entities, but exact entity_value is also accepted.",
            parameters={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "entity_value": {"type": "string"},
                },
                "additionalProperties": False,
            },
            risk_level="low",
            requires_approval=False,
        ),
        list_transforms,
    )
    registry.register(
        ToolDefinition(
            name="run_transform",
            description="Execute one OGI transform directly and persist its resulting entities and edges. Prefer entity_id from list_entities, but exact entity_value is also accepted.",
            parameters={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "entity_value": {"type": "string"},
                    "transform_name": {"type": "string"},
                    "config": {"type": "object"},
                },
                "required": ["transform_name"],
                "additionalProperties": False,
            },
            risk_level="high",
            requires_approval=True,
        ),
        run_transform,
    )
    registry.register(
        ToolDefinition(
            name="get_transform_result",
            description="Load the persisted result for a previous transform run.",
            parameters={
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
            risk_level="low",
            requires_approval=False,
        ),
        get_transform_result,
    )
    registry.register(
        ToolDefinition(
            name="finish_investigation",
            description="Finish the investigation and return a final summary.",
            parameters={
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
                "additionalProperties": False,
            },
            risk_level="low",
            requires_approval=False,
        ),
        finish_investigation,
    )
    return registry
