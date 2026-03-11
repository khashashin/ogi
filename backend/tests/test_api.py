import os
import pytest
from httpx import AsyncClient, ASGITransport

# Use in-memory SQLite DB for tests and disable Supabase auth
os.environ["OGI_DB_PATH"] = ":memory:"
os.environ["OGI_USE_SQLITE"] = "true"
os.environ["OGI_SUPABASE_URL"] = ""
os.environ["OGI_SUPABASE_ANON_KEY"] = ""
os.environ["OGI_SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["OGI_SUPABASE_JWT_SECRET"] = ""

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
    assert len(transforms) >= 15
    names = [t["name"] for t in transforms]
    assert "domain_to_ip" in names


@pytest.mark.asyncio
async def test_list_entity_types(client: AsyncClient):
    resp = await client.get("/api/v1/transforms/entity-types")
    assert resp.status_code == 200
    types = resp.json()
    assert len(types) == 19


@pytest.mark.asyncio
async def test_discover_empty(client: AsyncClient):
    """Discover returns empty list when no public projects exist."""
    resp = await client.get("/api/v1/discover")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_discover_returns_public_projects(client: AsyncClient):
    """Discover returns public projects but not private ones."""
    # Create a private project
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Private", "description": "secret", "is_public": False},
    )
    assert resp.status_code == 201

    # Create a public project
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Public", "description": "visible", "is_public": True},
    )
    assert resp.status_code == 201

    resp = await client.get("/api/v1/discover")
    assert resp.status_code == 200
    projects = resp.json()
    names = [p["name"] for p in projects]
    assert "Public" in names
    assert "Private" not in names


@pytest.mark.asyncio
async def test_bookmark_and_unbookmark(client: AsyncClient):
    """Bookmark and unbookmark a public project."""
    # Create a public project
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "BookmarkTarget", "is_public": True},
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    # Bookmark it
    resp = await client.post(f"/api/v1/projects/{project_id}/bookmark")
    assert resp.status_code == 201
    assert resp.json()["status"] == "bookmarked"

    # Bookmarking again should conflict
    resp = await client.post(f"/api/v1/projects/{project_id}/bookmark")
    assert resp.status_code == 409

    # Unbookmark
    resp = await client.delete(f"/api/v1/projects/{project_id}/bookmark")
    assert resp.status_code == 204

    # Unbookmarking again should 404
    resp = await client.delete(f"/api/v1/projects/{project_id}/bookmark")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_my_projects(client: AsyncClient):
    """GET /projects/my returns categorized projects."""
    # Create a project (will be 'owned')
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "MyOwned", "description": "mine"},
    )
    assert resp.status_code == 201

    resp = await client.get("/api/v1/projects/my")
    assert resp.status_code == 200
    projects = resp.json()
    assert isinstance(projects, list)
    # At least the project we just created should appear
    names = [p["name"] for p in projects]
    assert "MyOwned" in names
    # Each item should have source and role fields
    for p in projects:
        assert "source" in p
        assert "role" in p
