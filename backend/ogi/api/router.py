from fastapi import APIRouter

from ogi.api import projects, entities, edges, transforms, graph, export, import_, members, plugins, api_keys, discover, registry, websocket

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(projects.router)
api_router.include_router(entities.router)
api_router.include_router(edges.router)
api_router.include_router(transforms.router)
api_router.include_router(graph.router)
api_router.include_router(export.router)
api_router.include_router(import_.router)
api_router.include_router(members.router)
api_router.include_router(plugins.router)
api_router.include_router(api_keys.router)
api_router.include_router(discover.router)
api_router.include_router(registry.router)
api_router.include_router(websocket.router)

