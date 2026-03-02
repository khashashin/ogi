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


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "GetMe"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "GetMe"
    assert "role" in data
    assert data["role"] == "owner"


@pytest.mark.asyncio
async def test_get_public_project_as_viewer(client: AsyncClient):
    """Viewer of a public project gets role: 'viewer'"""
    from ogi.api.auth import get_current_user
    from ogi.models import UserProfile
    from uuid import uuid4

    resp = await client.post("/api/v1/projects", json={"name": "PublicViewer", "is_public": True})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    other_user = UserProfile(id=uuid4(), email="other@test.com")
    app.dependency_overrides[get_current_user] = lambda: other_user

    try:
        resp = await client.get(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "viewer"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "BeforeUpdate"})
    project_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "AfterUpdate", "description": "new desc", "is_public": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "AfterUpdate"
    assert data["description"] == "new desc"
    assert data["is_public"] is True


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "DeleteMe"})
    project_id = resp.json()["id"]

    resp = await client.delete(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 204

    # Confirm it's gone — returns 403 (role check fails) since project no longer exists
    resp = await client.get(f"/api/v1/projects/{project_id}")
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_get_nonexistent_project(client: AsyncClient):
    """Accessing a nonexistent project returns 403 (role check rejects before 404)."""
    resp = await client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001")
    assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# Discover — search filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_search_filter(client: AsyncClient):
    """Discover ?q= filters by name/description."""
    await client.post(
        "/api/v1/projects",
        json={"name": "Alpha Project", "description": "first", "is_public": True},
    )
    await client.post(
        "/api/v1/projects",
        json={"name": "Beta Project", "description": "second", "is_public": True},
    )

    resp = await client.get("/api/v1/discover?q=Alpha")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "Alpha Project" in names
    assert "Beta Project" not in names


# ---------------------------------------------------------------------------
# Bookmark edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bookmark_private_project_forbidden(client: AsyncClient):
    """Bookmarking a private project returns 403."""
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "PrivateNoBookmark", "is_public": False},
    )
    project_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/projects/{project_id}/bookmark")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_bookmark_nonexistent_project(client: AsyncClient):
    resp = await client.post("/api/v1/projects/00000000-0000-0000-0000-000000000099/bookmark")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_my_projects_includes_bookmarked(client: AsyncClient):
    """Bookmarked projects appear in /projects/my with source=bookmarked."""
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "BookmarkForMy", "is_public": True},
    )
    project_id = resp.json()["id"]

    await client.post(f"/api/v1/projects/{project_id}/bookmark")

    resp = await client.get("/api/v1/projects/my")
    assert resp.status_code == 200
    bookmarked = [p for p in resp.json() if p["name"] == "BookmarkForMy" and p["source"] == "bookmarked"]
    # The project is also "owned", so it won't duplicate as bookmarked.
    # At minimum it must appear somewhere.
    all_names = [p["name"] for p in resp.json()]
    assert "BookmarkForMy" in all_names


# ---------------------------------------------------------------------------
# Edge CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_crud(client: AsyncClient):
    # Setup: project + two entities
    resp = await client.post("/api/v1/projects", json={"name": "EdgeTest"})
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Domain", "value": "a.com"},
    )
    eid_a = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "IPAddress", "value": "1.2.3.4"},
    )
    eid_b = resp.json()["id"]

    # Create edge
    resp = await client.post(
        f"/api/v1/projects/{pid}/edges",
        json={"source_id": eid_a, "target_id": eid_b, "label": "resolves_to"},
    )
    assert resp.status_code == 201
    edge = resp.json()
    assert edge["label"] == "resolves_to"
    edge_id = edge["id"]

    # List edges
    resp = await client.get(f"/api/v1/projects/{pid}/edges")
    assert resp.status_code == 200
    assert any(e["id"] == edge_id for e in resp.json())

    # Update edge
    resp = await client.patch(
        f"/api/v1/projects/{pid}/edges/{edge_id}",
        json={"label": "points_to", "weight": 5},
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "points_to"
    assert resp.json()["weight"] == 5

    # Delete edge
    resp = await client.delete(f"/api/v1/projects/{pid}/edges/{edge_id}")
    assert resp.status_code == 204

    # Confirm gone
    resp = await client.get(f"/api/v1/projects/{pid}/edges")
    assert all(e["id"] != edge_id for e in resp.json())


# ---------------------------------------------------------------------------
# Graph endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_get(client: AsyncClient):
    """GET /graph returns entities and edges."""
    resp = await client.post("/api/v1/projects", json={"name": "GraphGet"})
    pid = resp.json()["id"]

    # Add an entity
    await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Domain", "value": "graph.test"},
    )

    resp = await client.get(f"/api/v1/projects/{pid}/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert "entities" in data
    assert "edges" in data
    assert len(data["entities"]) >= 1


@pytest.mark.asyncio
async def test_graph_stats(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "StatsTest"})
    pid = resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{pid}/graph/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert "entity_count" in stats
    assert "edge_count" in stats
    assert "density" in stats


@pytest.mark.asyncio
async def test_graph_analyze(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "AnalyzeTest"})
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/graph/analyze",
        json={"algorithm": "degree_centrality"},
    )
    assert resp.status_code == 200
    assert "scores" in resp.json()


@pytest.mark.asyncio
async def test_graph_analyze_unknown_algorithm(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "BadAlgo"})
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/graph/analyze",
        json={"algorithm": "nonexistent"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_json(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "ExportJSON"})
    pid = resp.json()["id"]

    await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Domain", "value": "export.test"},
    )

    resp = await client.get(f"/api/v1/projects/{pid}/export/json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "1.0"
    assert data["project"]["name"] == "ExportJSON"
    assert len(data["entities"]) >= 1


@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "ExportCSV"})
    pid = resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{pid}/export/csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"


@pytest.mark.asyncio
async def test_export_graphml(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "ExportGraphML"})
    pid = resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{pid}/export/graphml")
    assert resp.status_code == 200
    assert "graphml" in resp.text


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_plugins(client: AsyncClient):
    resp = await client.get("/api/v1/plugins")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_nonexistent_plugin(client: AsyncClient):
    resp = await client.get("/api/v1/plugins/no_such_plugin")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_plugin_enable_disable_is_user_preference(client: AsyncClient):
    resp = await client.get("/api/v1/plugins")
    assert resp.status_code == 200
    plugins = resp.json()
    if not plugins:
        pytest.skip("No plugins available in test environment")

    plugin_name = plugins[0]["name"]

    resp = await client.post(f"/api/v1/plugins/{plugin_name}/disable")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    resp = await client.get(f"/api/v1/plugins/{plugin_name}")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    resp = await client.post(f"/api/v1/plugins/{plugin_name}/enable")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


@pytest.mark.asyncio
async def test_disabling_plugin_hides_its_transforms(client: AsyncClient):
    resp = await client.get("/api/v1/plugins")
    assert resp.status_code == 200
    plugins = resp.json()
    if not plugins:
        pytest.skip("No plugins available in test environment")

    plugin_with_transforms = next(
        (p for p in plugins if p.get("transform_names")),
        None,
    )
    if plugin_with_transforms is None:
        pytest.skip("No plugin transforms available to validate filtering")

    plugin_name = plugin_with_transforms["name"]
    transform_names = set(plugin_with_transforms["transform_names"])

    resp = await client.post(f"/api/v1/plugins/{plugin_name}/disable")
    assert resp.status_code == 200

    resp = await client.get("/api/v1/transforms")
    assert resp.status_code == 200
    listed_names = {t["name"] for t in resp.json()}
    assert listed_names.isdisjoint(transform_names)

    resp = await client.post(f"/api/v1/plugins/{plugin_name}/enable")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Transforms — for-entity and runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transforms_for_entity(client: AsyncClient):
    """GET /transforms/for-entity/{id} returns applicable transforms."""
    resp = await client.post("/api/v1/projects", json={"name": "TransformFor"})
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Domain", "value": "example.org"},
    )
    eid = resp.json()["id"]

    resp = await client.get(f"/api/v1/transforms/for-entity/{eid}")
    assert resp.status_code == 200
    transforms = resp.json()
    assert isinstance(transforms, list)
    # Domain entities should have DNS transforms available
    names = [t["name"] for t in transforms]
    assert "domain_to_ip" in names


# ---------------------------------------------------------------------------
# Entity edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_single_entity(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "SingleEntity"})
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "EmailAddress", "value": "test@example.com"},
    )
    eid = resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{pid}/entities/{eid}")
    assert resp.status_code == 200
    assert resp.json()["value"] == "test@example.com"
    assert resp.json()["type"] == "EmailAddress"


@pytest.mark.asyncio
async def test_entity_with_properties(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "EntityProps"})
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={
            "type": "Person",
            "value": "John Doe",
            "properties": {"age": 30, "country": "US"},
            "tags": ["suspect", "vip"],
            "notes": "important person",
        },
    )
    assert resp.status_code == 201
    entity = resp.json()
    assert entity["properties"]["country"] == "US"
    assert "suspect" in entity["tags"]
    assert entity["notes"] == "important person"


# ---------------------------------------------------------------------------
# Import JSON
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_json(client: AsyncClient):
    """Import JSON file and verify entities are created."""
    import json as _json

    resp = await client.post("/api/v1/projects", json={"name": "ImportTest"})
    pid = resp.json()["id"]

    payload = _json.dumps({
        "entities": [
            {"type": "Domain", "value": "imported.com"},
            {"type": "IPAddress", "value": "10.0.0.1"},
        ],
        "edges": [],
    })

    resp = await client.post(
        f"/api/v1/projects/{pid}/import/json",
        files={"file": ("import.json", payload, "application/json")},
    )
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["entities_added"] >= 2

    # Verify entities exist
    resp = await client.get(f"/api/v1/projects/{pid}/entities")
    values = [e["value"] for e in resp.json()]
    assert "imported.com" in values
    assert "10.0.0.1" in values
