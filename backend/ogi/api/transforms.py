from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ogi.models import TransformInfo, TransformRun, EdgeCreate
from ogi.transforms.base import TransformConfig
from ogi.api.dependencies import (
    get_transform_engine,
    get_entity_store,
    get_entity_registry,
    get_edge_store,
    get_graph_engine,
    get_transform_run_store,
)

router = APIRouter(prefix="/transforms", tags=["transforms"])


class RunTransformRequest(BaseModel):
    entity_id: UUID
    project_id: UUID
    config: TransformConfig = Field(default_factory=TransformConfig)


@router.get("", response_model=list[TransformInfo])
async def list_transforms() -> list[TransformInfo]:
    engine = get_transform_engine()
    return engine.list_transforms()


@router.get("/entity-types")
async def list_entity_types() -> list[dict[str, str]]:
    registry = get_entity_registry()
    return registry.list_types_dict()


@router.get("/for-entity/{entity_id}", response_model=list[TransformInfo])
async def list_transforms_for_entity(entity_id: UUID) -> list[TransformInfo]:
    entity_store = get_entity_store()
    entity = await entity_store.get(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    engine = get_transform_engine()
    return engine.list_for_entity(entity)


@router.post("/{name}/run", response_model=TransformRun)
async def run_transform(name: str, request: RunTransformRequest) -> TransformRun:
    entity_store = get_entity_store()
    entity = await entity_store.get(request.entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    transform_engine = get_transform_engine()
    try:
        run = await transform_engine.run_transform(
            name, entity, request.project_id, request.config
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Persist discovered entities and edges, deduplicating by type+value
    if run.result:
        es = get_entity_store()
        edge_s = get_edge_store()
        graph = get_graph_engine(request.project_id)

        # Map transform-generated IDs to actual persisted IDs (may differ if deduplicated)
        id_map: dict[UUID, UUID] = {}

        for new_entity in run.result.entities:
            saved = await es.save(request.project_id, new_entity)
            id_map[new_entity.id] = saved.id
            if not graph.get_entity(saved.id):
                graph.add_entity(saved)

        for new_edge in run.result.edges:
            # Remap edge endpoints to the actual persisted entity IDs
            actual_source = id_map.get(new_edge.source_id, new_edge.source_id)
            actual_target = id_map.get(new_edge.target_id, new_edge.target_id)

            # Skip duplicate edges
            existing_edges = graph.get_edges_for_entity(actual_source) if graph.get_entity(actual_source) else []
            is_duplicate = any(
                e.source_id == actual_source and e.target_id == actual_target and e.label == new_edge.label
                for e in existing_edges
            )
            if is_duplicate:
                continue

            edge_data = EdgeCreate(
                source_id=actual_source,
                target_id=actual_target,
                label=new_edge.label,
                source_transform=new_edge.source_transform,
            )
            saved_edge = await edge_s.create(request.project_id, edge_data)
            try:
                graph.add_edge(saved_edge)
            except ValueError:
                pass

        # Update the result to reflect deduplicated IDs so the frontend gets correct data
        persisted_entity_ids = {id_map.get(e.id, e.id) for e in run.result.entities}
        # Include the input entity so edges connecting to it are found
        persisted_entity_ids.add(entity.id)

        run.result.entities = [
            es_entity for eid in persisted_entity_ids
            if eid != entity.id and (es_entity := graph.get_entity(eid)) is not None
        ]
        # Return all edges where both endpoints are in the set of involved entities
        run.result.edges = [
            e for e in graph.edges.values()
            if e.source_id in persisted_entity_ids and e.target_id in persisted_entity_ids
        ]

    # Persist the run
    run_store = get_transform_run_store()
    await run_store.save(run)

    return run


@router.get("/runs/{run_id}", response_model=TransformRun)
async def get_run(run_id: UUID) -> TransformRun:
    # Try in-memory first, then DB
    engine = get_transform_engine()
    run = engine.get_run(run_id)
    if run is not None:
        return run
    run_store = get_transform_run_store()
    run = await run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Transform run not found")
    return run


@router.get("/project/{project_id}/runs", response_model=list[TransformRun])
async def list_project_runs(project_id: UUID) -> list[TransformRun]:
    run_store = get_transform_run_store()
    return await run_store.list_by_project(project_id)
