import os
import pytest
from httpx import AsyncClient, ASGITransport

# Use in-memory SQLite DB for tests
os.environ.setdefault("OGI_DB_PATH", ":memory:")
os.environ.setdefault("OGI_USE_SQLITE", "true")

from ogi.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Trigger lifespan startup manually
        async with app.router.lifespan_context(app):
            yield c


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_and_list_projects(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "Test", "description": "desc"})
    assert resp.status_code == 201
    project = resp.json()
    assert project["name"] == "Test"

    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 200
    projects = resp.json()
    assert len(projects) >= 1


@pytest.mark.asyncio
async def test_entity_crud(client: AsyncClient):
    # Create project
    resp = await client.post("/api/v1/projects", json={"name": "EntityTest"})
    project_id = resp.json()["id"]

    # Create entity
    resp = await client.post(
        f"/api/v1/projects/{project_id}/entities",
        json={"type": "Domain", "value": "example.com"},
    )
    assert resp.status_code == 201
    entity = resp.json()
    assert entity["value"] == "example.com"
    assert entity["type"] == "Domain"
    entity_id = entity["id"]

    # List entities
    resp = await client.get(f"/api/v1/projects/{project_id}/entities")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # Update entity
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/entities/{entity_id}",
        json={"notes": "test note"},
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "test note"

    # Delete entity
    resp = await client.delete(f"/api/v1/projects/{project_id}/entities/{entity_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_list_transforms(client: AsyncClient):
    resp = await client.get("/api/v1/transforms")
    assert resp.status_code == 200
    transforms = resp.json()
    assert len(transforms) == 15
    names = [t["name"] for t in transforms]
    assert "domain_to_ip" in names


@pytest.mark.asyncio
async def test_list_entity_types(client: AsyncClient):
    resp = await client.get("/api/v1/transforms/entity-types")
    assert resp.status_code == 200
    types = resp.json()
    assert len(types) == 19
