from fastapi import APIRouter

from ogi.api import projects, entities, edges, transforms, graph, export, import_

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(projects.router)
api_router.include_router(entities.router)
api_router.include_router(edges.router)
api_router.include_router(transforms.router)
api_router.include_router(graph.router)
api_router.include_router(export.router)
api_router.include_router(import_.router)
