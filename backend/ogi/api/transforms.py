from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ogi.models import TransformInfo, TransformRun
from ogi.transforms.base import TransformConfig
from ogi.api.dependencies import (
    get_transform_engine,
    get_entity_store,
    get_entity_registry,
    get_edge_store,
    get_graph_engine,
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

    # Persist discovered entities and edges
    if run.result:
        es = get_entity_store()
        edge_s = get_edge_store()
        graph = get_graph_engine(request.project_id)

        for new_entity in run.result.entities:
            new_entity.project_id = request.project_id
            await es.create(
                request.project_id,
                __import__("ogi.models", fromlist=["EntityCreate"]).EntityCreate(
                    type=new_entity.type,
                    value=new_entity.value,
                    properties=new_entity.properties,
                    source=new_entity.source,
                ),
            )
            graph.add_entity(new_entity)

        for new_edge in run.result.edges:
            new_edge.project_id = request.project_id
            try:
                graph.add_edge(new_edge)
            except ValueError:
                pass
            await edge_s.create(
                request.project_id,
                __import__("ogi.models", fromlist=["EdgeCreate"]).EdgeCreate(
                    source_id=new_edge.source_id,
                    target_id=new_edge.target_id,
                    label=new_edge.label,
                    source_transform=new_edge.source_transform,
                ),
            )

    return run


@router.get("/runs/{run_id}", response_model=TransformRun)
async def get_run(run_id: UUID) -> TransformRun:
    engine = get_transform_engine()
    run = engine.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Transform run not found")
    return run
