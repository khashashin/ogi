from __future__ import annotations

from typing import Any
from uuid import UUID
from uuid import UUID as UUIDType

from fastapi import HTTPException

from ogi.agent.store import AgentRunStore
from ogi.agent.tools import ToolContext, ToolDefinition, ToolRegistry, ToolResult
from ogi.engine.plugin_engine import PluginEngine
from ogi.engine.transform_engine import TransformEngine
from ogi.engine.transform_execution_service import TransformExecutionService
from ogi.models import AuditLogCreate, TransformInfo
from ogi.models.edge import EdgeCreate
from ogi.models.entity import EntityCreate
from ogi.models import EntityType
from ogi.store.audit_log_store import AuditLogStore
from ogi.store.edge_store import EdgeStore
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
        if matches:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Entity '{entity_value}' not found as an exact entity value in the investigation scope. "
                    "This may be a property value rather than a graph entity. Use entity_id from search_graph/list_entities, "
                    "or create a new entity explicitly before requesting transforms."
                ),
            )
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
                },
                "guidance": (
                    "Entity properties are metadata on this entity. Property values such as profile_url are not "
                    "guaranteed to exist as standalone graph entities unless they are returned separately by "
                    "list_entities, search_graph, or created explicitly."
                ),
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
        entity_id, entity = await _resolve_entity(ctx, params)
        transform_name = str(params["transform_name"])
        overrides = params.get("config", {})
        if not isinstance(overrides, dict):
            raise HTTPException(status_code=400, detail="config must be an object")
        available_transforms = transform_engine.list_for_entity(entity)
        available_names = [item.name for item in available_transforms]
        if transform_name not in available_names:
            available_text = ", ".join(sorted(available_names)) if available_names else "none"
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Transform '{transform_name}' is not available for entity '{entity.value}' ({entity.type.value}). "
                    f"Use an exact name from list_transforms. Available transforms: {available_text}"
                ),
            )
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

    async def create_entity(params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        raw_type = str(params.get("type") or "").strip()
        raw_value = str(params.get("value") or "").strip()
        if not raw_type:
            raise HTTPException(status_code=400, detail="type is required")
        if not raw_value:
            raise HTTPException(status_code=400, detail="value is required")

        try:
            entity_type = EntityType(raw_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Unsupported entity type '{raw_type}'") from exc

        raw_properties = params.get("properties") or {}
        if not isinstance(raw_properties, dict):
            raise HTTPException(status_code=400, detail="properties must be an object")

        raw_tags = params.get("tags") or []
        if raw_tags and not isinstance(raw_tags, list):
            raise HTTPException(status_code=400, detail="tags must be an array")

        notes = str(params.get("notes") or "").strip()
        reason = str(params.get("reason") or "").strip()
        edge_label = str(params.get("edge_label") or "").strip() or "derived"
        source_property = str(params.get("source_property") or "").strip()

        entity_store = EntityStore(ctx.session)
        edge_store = EdgeStore(ctx.session)
        audit_store = AuditLogStore(ctx.session)
        run_store = AgentRunStore(ctx.session)

        link_entity_id: UUID | None = None
        link_entity = None
        if params.get("link_to_entity_id") or params.get("link_to_entity_value"):
            link_params = {
                "entity_id": params.get("link_to_entity_id"),
                "entity_value": params.get("link_to_entity_value"),
            }
            link_entity_id, link_entity = await _resolve_entity(ctx, link_params)

        properties = {str(key): value for key, value in raw_properties.items()}
        if reason and "creation_reason" not in properties:
            properties["creation_reason"] = reason
        if source_property and "source_property" not in properties:
            properties["source_property"] = source_property

        created = await entity_store.create(
            ctx.project_id,
            EntityCreate(
                type=entity_type,
                value=raw_value,
                properties=properties,
                notes=notes,
                tags=[str(item).strip() for item in raw_tags if str(item).strip()],
                source="agent",
                origin_source="agent",
            ),
        )

        created_edge = None
        if link_entity_id is not None and link_entity is not None and link_entity_id != created.id:
            created_edge = await edge_store.create(
                ctx.project_id,
                EdgeCreate(
                    source_id=link_entity_id,
                    target_id=created.id,
                    label=edge_label,
                    properties={
                        "created_by_agent": True,
                        "reason": reason,
                        "source_property": source_property,
                    },
                    source_transform="agent.create_entity",
                ),
            )

        if ctx.scope.mode == "selected":
            run = await run_store.get(ctx.run_id)
            if run is not None:
                scope_ids = [UUID(str(value)) for value in run.scope.get("entity_ids", [])]
                if created.id not in scope_ids:
                    scope_ids.append(created.id)
                    run.scope = {
                        "mode": "selected",
                        "entity_ids": [str(item) for item in scope_ids],
                    }
                    await run_store.save(run)

        await audit_store.create(
            ctx.project_id,
            ctx.user_id,
            AuditLogCreate(
                action="agent.entity_created",
                resource_type="entity",
                resource_id=str(created.id),
                details={
                    "run_id": str(ctx.run_id),
                    "entity_type": created.type.value,
                    "entity_value": created.value,
                    "linked_from_entity_id": None if link_entity_id is None else str(link_entity_id),
                    "linked_from_entity_value": None if link_entity is None else link_entity.value,
                    "reason": reason,
                    "source_property": source_property,
                },
            ),
        )

        return ToolResult(
            data={
                "entity": {
                    "id": str(created.id),
                    "type": created.type.value,
                    "value": created.value,
                    "properties": created.properties,
                    "notes": created.notes,
                    "tags": created.tags,
                },
                "edge": None
                if created_edge is None
                else {
                    "id": str(created_edge.id),
                    "source_id": str(created_edge.source_id),
                    "target_id": str(created_edge.target_id),
                    "label": created_edge.label,
                },
            },
            summary=(
                f"Created or reused entity {created.value} ({created.type.value})"
                + (f" linked from {link_entity.value}." if link_entity is not None else ".")
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
            description="Search entity values inside the current project scope. Search is fuzzy and does not guarantee that the query itself is an exact entity value.",
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
            description="List transforms that can run on a specific entity. Prefer entity_id from list_entities or search_graph. Entity properties like profile_url are not guaranteed to be standalone entities.",
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
            description="Execute one OGI transform directly and persist its resulting entities and edges. Prefer entity_id from list_entities, but exact entity_value is also accepted. Transform names must exactly match names returned by list_transforms for that entity.",
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
            name="create_entity",
            description="Create a new graph entity from an actionable property or discovered value, and optionally link it to an existing entity. Use this when a property value is useful but not already present as a graph entity.",
            parameters={
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "value": {"type": "string"},
                    "properties": {"type": "object"},
                    "notes": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                    "source_property": {"type": "string"},
                    "link_to_entity_id": {"type": "string"},
                    "link_to_entity_value": {"type": "string"},
                    "edge_label": {"type": "string"},
                },
                "required": ["type", "value"],
                "additionalProperties": False,
            },
            risk_level="high",
            requires_approval=True,
        ),
        create_entity,
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
