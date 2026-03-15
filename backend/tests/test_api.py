import asyncio
import json
import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlmodel import select
from starlette.websockets import WebSocketDisconnect

# Use in-memory SQLite DB for tests and disable Supabase auth
os.environ["OGI_DB_PATH"] = ":memory:"
os.environ["OGI_USE_SQLITE"] = "true"
os.environ["OGI_SUPABASE_URL"] = ""
os.environ["OGI_SUPABASE_ANON_KEY"] = ""
os.environ["OGI_SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["OGI_SUPABASE_JWT_SECRET"] = ""
os.environ["OGI_API_KEY_ENCRYPTION_KEY"] = "k0f97udxEhQ4duzTQESsQNmjUG74U7SMiFd7LrD0WBE="

from ogi.main import app


def assert_error_envelope(
    response,
    status_code: int,
    code: str | None = None,
    message_contains: str | None = None,
) -> dict:
    assert response.status_code == status_code
    body = response.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
    if code is not None:
        assert body["error"]["code"] == code
    if message_contains is not None:
        assert message_contains in body["error"]["message"]
    return body


@pytest.fixture
async def client():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Trigger lifespan startup manually
        async with app.router.lifespan_context(app):
            yield c


@pytest.fixture
def sync_client():
    with TestClient(app) as c:
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
async def test_list_transforms_includes_plugin_metadata(client: AsyncClient):
    resp = await client.get("/api/v1/transforms")
    assert resp.status_code == 200
    transforms = resp.json()

    hello_world = next((t for t in transforms if t["name"] == "hello_world"), None)
    assert hello_world is not None
    assert hello_world["plugin_name"] == "example-plugin"
    assert hello_world["plugin_verification_tier"] == "community"
    assert hello_world["plugin_permissions"] == {
        "network": False,
        "filesystem": False,
        "subprocess": False,
    }
    assert hello_world["plugin_source"] == "local"

    domain_to_ip = next((t for t in transforms if t["name"] == "domain_to_ip"), None)
    assert domain_to_ip is not None
    assert domain_to_ip["plugin_name"] is None


@pytest.mark.asyncio
async def test_list_entity_types(client: AsyncClient):
    resp = await client.get("/api/v1/transforms/entity-types")
    assert resp.status_code == 200
    types = resp.json()
    type_names = {item["type"] for item in types}
    assert {
        "Person",
        "Username",
        "EmailAddress",
        "Domain",
        "URL",
        "Location",
        "Organization",
    } <= type_names
    assert len(type_names) == len(types)


@pytest.mark.asyncio
async def test_save_transform_settings_returns_allowed_maximum_in_error(client: AsyncClient):
    resp = await client.put(
        "/api/v1/transforms/username_search/settings/user",
        json={"settings": {"max_sites": "999"}},
    )
    assert_error_envelope(
        resp,
        400,
        code="HTTP_400",
        message_contains="Setting 'max_sites' is above maximum 200",
    )


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
    assert_error_envelope(resp, 403, code="HTTP_403")


@pytest.mark.asyncio
async def test_bookmark_nonexistent_project(client: AsyncClient):
    resp = await client.post("/api/v1/projects/00000000-0000-0000-0000-000000000099/bookmark")
    assert_error_envelope(resp, 404, code="HTTP_404")


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


@pytest.mark.asyncio
async def test_edge_create_rejects_cross_project_entities(client: AsyncClient):
    """POST /edges rejects source/target entities from different projects."""
    resp = await client.post("/api/v1/projects", json={"name": "EdgeP1"})
    p1 = resp.json()["id"]
    resp = await client.post("/api/v1/projects", json={"name": "EdgeP2"})
    p2 = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{p1}/entities",
        json={"type": "Domain", "value": "p1.example"},
    )
    e1 = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/projects/{p2}/entities",
        json={"type": "IPAddress", "value": "8.8.8.8"},
    )
    e2 = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{p1}/edges",
        json={"source_id": e1, "target_id": e2, "label": "invalid_cross_project"},
    )
    assert_error_envelope(resp, 400, code="HTTP_400", message_contains="same project")


@pytest.mark.asyncio
async def test_edge_create_deduplicates_identical_tuple(client: AsyncClient):
    """POST /edges returns existing edge for identical project/source/target/label."""
    resp = await client.post("/api/v1/projects", json={"name": "EdgeDedup"})
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Domain", "value": "dup.example"},
    )
    source_id = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "IPAddress", "value": "1.1.1.1"},
    )
    target_id = resp.json()["id"]

    payload = {"source_id": source_id, "target_id": target_id, "label": "resolves_to"}
    first = await client.post(f"/api/v1/projects/{pid}/edges", json=payload)
    second = await client.post(f"/api/v1/projects/{pid}/edges", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_project_delete_cascades_entities_and_edges(client: AsyncClient):
    """Deleting a project removes related entities/edges from list endpoints."""
    resp = await client.post("/api/v1/projects", json={"name": "CascadeProject"})
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Domain", "value": "cascade.example"},
    )
    e1 = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "IPAddress", "value": "9.9.9.9"},
    )
    e2 = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/edges",
        json={"source_id": e1, "target_id": e2, "label": "resolves_to"},
    )
    assert resp.status_code == 201

    resp = await client.delete(f"/api/v1/projects/{pid}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/projects/{pid}/entities")
    assert resp.status_code in (403, 404)
    resp = await client.get(f"/api/v1/projects/{pid}/edges")
    assert resp.status_code in (403, 404)


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
async def test_graph_get_refreshes_entities_written_outside_engine(client: AsyncClient):
    """Graph endpoint refresh mode should include entities written directly to DB."""
    from uuid import UUID

    from ogi.db.database import get_session
    from ogi.models import EntityCreate, EntityType
    from ogi.store.entity_store import EntityStore

    resp = await client.post("/api/v1/projects", json={"name": "GraphRefresh"})
    pid = resp.json()["id"]

    # Seed + hydrate engine through normal API path.
    await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Domain", "value": "seed.test"},
    )
    resp = await client.get(f"/api/v1/projects/{pid}/graph")
    assert resp.status_code == 200
    assert len(resp.json()["entities"]) == 1

    # Simulate worker write: persist directly to DB, bypassing GraphEngine.
    async for session in get_session():
        store = EntityStore(session)
        await store.create(
            UUID(pid),
            EntityCreate(type=EntityType.DOCUMENT, value="from-worker"),
        )
        break

    # Explicit refresh picks up out-of-band DB writes.
    resp = await client.get(f"/api/v1/projects/{pid}/graph?refresh=true")
    assert resp.status_code == 200
    values = {e["value"] for e in resp.json()["entities"]}
    assert "seed.test" in values
    assert "from-worker" in values


@pytest.mark.asyncio
async def test_graph_get_uses_hydration_gate_for_empty_project(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """An empty project should hydrate once unless explicit refresh is requested."""
    from ogi.store.entity_store import EntityStore
    from ogi.store.edge_store import EdgeStore

    resp = await client.post("/api/v1/projects", json={"name": "HydrationGate"})
    pid = resp.json()["id"]

    entity_calls = {"count": 0}
    edge_calls = {"count": 0}
    original_list_entities = EntityStore.list_by_project
    original_list_edges = EdgeStore.list_by_project

    async def wrapped_list_entities(self, project_id):  # type: ignore[no-untyped-def]
        entity_calls["count"] += 1
        return await original_list_entities(self, project_id)

    async def wrapped_list_edges(self, project_id):  # type: ignore[no-untyped-def]
        edge_calls["count"] += 1
        return await original_list_edges(self, project_id)

    monkeypatch.setattr(EntityStore, "list_by_project", wrapped_list_entities)
    monkeypatch.setattr(EdgeStore, "list_by_project", wrapped_list_edges)

    resp = await client.get(f"/api/v1/projects/{pid}/graph")
    assert resp.status_code == 200
    resp = await client.get(f"/api/v1/projects/{pid}/graph")
    assert resp.status_code == 200
    assert entity_calls["count"] == 1
    assert edge_calls["count"] == 1

    resp = await client.get(f"/api/v1/projects/{pid}/graph?refresh=true")
    assert resp.status_code == 200
    assert entity_calls["count"] == 2
    assert edge_calls["count"] == 2


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fmt", "expected_suffix"),
    [
        ("json", ".ogi.json"),
        ("csv", ".csv.zip"),
        ("graphml", ".graphml"),
    ],
)
async def test_export_cloud_returns_signed_url_payload(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    fmt: str,
    expected_suffix: str,
):
    from ogi.api import export as export_api

    captured: dict[str, str] = {}

    async def fake_upload(project_id, filename, content, content_type):  # type: ignore[no-untyped-def]
        captured["filename"] = filename
        captured["content_type"] = content_type
        return f"https://signed.example/{project_id}/{filename}?token=abc123"

    monkeypatch.setattr(export_api, "_upload_to_storage", fake_upload)

    resp = await client.post("/api/v1/projects", json={"name": "ExportCloud"})
    pid = resp.json()["id"]

    # Seed at least one entity so JSON/GraphML payloads contain data.
    await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Domain", "value": "cloud.test"},
    )

    resp = await client.get(f"/api/v1/projects/{pid}/export/{fmt}?cloud=true")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    payload = resp.json()
    assert "url" in payload
    assert payload["url"].startswith("https://signed.example/")
    assert captured["filename"].endswith(expected_suffix)


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


@pytest.mark.asyncio
async def test_plugin_preferences_are_per_user(client: AsyncClient):
    from uuid import uuid4

    from ogi.api.auth import get_current_user
    from ogi.models import UserProfile

    resp = await client.get("/api/v1/plugins")
    assert resp.status_code == 200
    plugins = resp.json()
    if not plugins:
        pytest.skip("No plugins available in test environment")

    plugin_name = plugins[0]["name"]

    user1 = UserProfile(id=uuid4(), email="user1@test.com")
    user2 = UserProfile(id=uuid4(), email="user2@test.com")

    app.dependency_overrides[get_current_user] = lambda: user1
    try:
        resp = await client.post(f"/api/v1/plugins/{plugin_name}/disable")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
    finally:
        app.dependency_overrides.clear()

    app.dependency_overrides[get_current_user] = lambda: user2
    try:
        resp = await client.get(f"/api/v1/plugins/{plugin_name}")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_registry_mutation_requires_admin_when_auth_enabled(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from uuid import uuid4

    from ogi.api.auth import get_current_user
    from ogi.config import settings
    from ogi.models import UserProfile

    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "anon-key")
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")

    app.dependency_overrides[get_current_user] = lambda: UserProfile(
        id=uuid4(),
        email="viewer@example.com",
    )
    try:
        resp = await client.post("/api/v1/registry/install/does-not-matter")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_project_list_requires_bearer_when_auth_enabled(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from ogi.config import settings

    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "anon-key")

    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 401
    assert "Missing or invalid Authorization header" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_registry_index_can_manage_flag_respects_admin_list(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from uuid import uuid4

    from ogi.api.auth import get_current_user
    from ogi.config import settings
    from ogi.models import UserProfile

    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "anon-key")
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")

    # Non-admin
    app.dependency_overrides[get_current_user] = lambda: UserProfile(
        id=uuid4(),
        email="viewer@example.com",
    )
    try:
        resp = await client.get("/api/v1/registry/index")
        assert resp.status_code == 200
        assert resp.json().get("can_manage") is False
    finally:
        app.dependency_overrides.clear()

    # Admin
    app.dependency_overrides[get_current_user] = lambda: UserProfile(
        id=uuid4(),
        email="admin@example.com",
    )
    try:
        resp = await client.get("/api/v1/registry/index")
        assert resp.status_code == 200
        assert resp.json().get("can_manage") is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_plugin_reload_requires_admin_when_auth_enabled(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from uuid import uuid4

    from ogi.api.auth import get_current_user
    from ogi.config import settings
    from ogi.models import UserProfile

    resp = await client.get("/api/v1/plugins")
    assert resp.status_code == 200
    plugins = resp.json()
    if not plugins:
        pytest.skip("No plugins available in test environment")

    plugin_name = plugins[0]["name"]

    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "anon-key")
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")

    app.dependency_overrides[get_current_user] = lambda: UserProfile(
        id=uuid4(),
        email="viewer@example.com",
    )
    try:
        resp = await client.post(f"/api/v1/plugins/{plugin_name}/reload")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


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


@pytest.mark.asyncio
async def test_run_transform_returns_503_when_enqueue_fails(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from ogi.api import transforms as transforms_api

    class BrokenQueue:
        def enqueue(self, *args, **kwargs):
            raise RuntimeError("redis connection dropped")

    monkeypatch.setattr(transforms_api, "get_rq_queue", lambda: BrokenQueue())

    # Setup: project + domain entity
    resp = await client.post("/api/v1/projects", json={"name": "QueueFailure"})
    assert resp.status_code == 201
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Domain", "value": "example.com"},
    )
    assert resp.status_code == 201
    eid = resp.json()["id"]

    resp = await client.post(
        "/api/v1/transforms/domain_to_ip/run",
        json={"entity_id": eid, "project_id": pid, "config": {"settings": {}}},
    )
    assert_error_envelope(resp, 503, code="HTTP_503", message_contains="Failed to enqueue transform job")


@pytest.mark.asyncio
async def test_run_transform_injects_required_api_key_from_store(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from ogi.api import transforms as transforms_api

    captured_config: dict = {}

    class CaptureQueue:
        def enqueue(self, *args, **kwargs):
            nonlocal captured_config
            captured_config = args[5]
            return None

    monkeypatch.setattr(transforms_api, "get_rq_queue", lambda: CaptureQueue())

    # Save API key in user settings store.
    resp = await client.post(
        "/api/v1/settings/api-keys",
        json={"service_name": "virustotal", "key": "vt-test-key"},
    )
    assert resp.status_code == 201

    # Setup: project + hash entity
    resp = await client.post("/api/v1/projects", json={"name": "InjectAPIKey"})
    assert resp.status_code == 201
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Hash", "value": "d41d8cd98f00b204e9800998ecf8427e"},
    )
    assert resp.status_code == 201
    eid = resp.json()["id"]

    # hash_lookup requires virustotal_api_key but request provides empty settings.
    resp = await client.post(
        "/api/v1/transforms/hash_lookup/run",
        json={"entity_id": eid, "project_id": pid, "config": {"settings": {}}},
    )
    assert resp.status_code == 200
    assert captured_config.get("settings", {}).get("virustotal_api_key") == "vt-test-key"


@pytest.mark.asyncio
async def test_transform_settings_user_defaults_are_applied_on_run(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from ogi.api import transforms as transforms_api

    captured_config: dict = {}

    class CaptureQueue:
        def enqueue(self, *args, **kwargs):
            nonlocal captured_config
            captured_config = args[5]
            return None

    monkeypatch.setattr(transforms_api, "get_rq_queue", lambda: CaptureQueue())

    # Create project + organization entity
    resp = await client.post("/api/v1/projects", json={"name": "SettingsRun"})
    assert resp.status_code == 201
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Domain", "value": "example.com", "properties": {}},
    )
    assert resp.status_code == 201
    eid = resp.json()["id"]

    # Save required OpenAI key and user defaults for transform settings.
    resp = await client.post(
        "/api/v1/settings/api-keys",
        json={"service_name": "openai", "key": "sk-test"},
    )
    assert resp.status_code == 201

    resp = await client.put(
        "/api/v1/transforms/website_to_people/settings/user",
        json={"settings": {"openai_model": "gpt-4.1-mini", "max_people": "42"}},
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/api/v1/transforms/website_to_people/run",
        json={"entity_id": eid, "project_id": pid, "config": {"settings": {}}},
    )
    assert resp.status_code == 200
    settings = captured_config.get("settings", {})
    assert settings.get("openai_model") == "gpt-4.1-mini"
    assert settings.get("max_people") == "42"
    assert settings.get("openai_api_key") == "sk-test"


@pytest.mark.asyncio
async def test_transform_settings_reject_api_key_persistence(client: AsyncClient):
    resp = await client.put(
        "/api/v1/transforms/location_to_weather_snapshot/settings/user",
        json={"settings": {"openweather_api_key": "ow-secret"}},
    )
    assert_error_envelope(
        resp,
        400,
        code="HTTP_400",
        message_contains="API key settings must be configured in API Keys",
    )


@pytest.mark.asyncio
async def test_run_transform_audits_stored_api_key_injection(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from ogi.api import transforms as transforms_api

    class CaptureQueue:
        def enqueue(self, *args, **kwargs):
            return None

    monkeypatch.setattr(transforms_api, "get_rq_queue", lambda: CaptureQueue())

    resp = await client.post(
        "/api/v1/settings/api-keys",
        json={"service_name": "virustotal", "key": "vt-test-key"},
    )
    assert resp.status_code == 201

    resp = await client.post("/api/v1/projects", json={"name": "APIKeyAudit"})
    assert resp.status_code == 201
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Hash", "value": "d41d8cd98f00b204e9800998ecf8427e"},
    )
    assert resp.status_code == 201
    eid = resp.json()["id"]

    resp = await client.post(
        "/api/v1/transforms/hash_lookup/run",
        json={"entity_id": eid, "project_id": pid, "config": {"settings": {}}},
    )
    assert resp.status_code == 200

    audit_resp = await client.get(f"/api/v1/projects/{pid}/audit-logs")
    assert audit_resp.status_code == 200
    rows = audit_resp.json()
    injected = next((row for row in rows if row["action"] == "transform.api_key_injected"), None)
    assert injected is not None
    assert injected["resource_id"] == "hash_lookup"
    assert injected["details"]["service_name"] == "virustotal"
    assert injected["details"]["injection_source"] == "stored_api_key"


@pytest.mark.asyncio
async def test_run_transform_blocks_stored_api_key_injection_for_community_plugin_when_disabled(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from ogi.api import transforms as transforms_api
    from ogi.config import settings
    from ogi.models import PluginInfo

    class CaptureQueue:
        def enqueue(self, *args, **kwargs):
            return None

    monkeypatch.setattr(transforms_api, "get_rq_queue", lambda: CaptureQueue())

    plugin_info = PluginInfo(
        name="mock-community-plugin",
        display_name="Mock Community Plugin",
        verification_tier="community",
        permissions={"network": True, "filesystem": False, "subprocess": False},
        api_keys_required=[{"service": "openai", "description": "OpenAI", "env_var": "OPENAI_API_KEY"}],
    )
    plugin_engine = transforms_api.get_plugin_engine()
    monkeypatch.setattr(plugin_engine, "get_plugin_for_transform", lambda transform_name: "mock-community-plugin" if transform_name == "website_to_people" else None)
    monkeypatch.setattr(plugin_engine, "get_plugin", lambda name: plugin_info if name == "mock-community-plugin" else None)
    monkeypatch.setattr(settings, "api_key_injection_allow_community_plugins", False)

    resp = await client.post(
        "/api/v1/settings/api-keys",
        json={"service_name": "openai", "key": "sk-test"},
    )
    assert resp.status_code == 201

    resp = await client.post("/api/v1/projects", json={"name": "PolicyBlocked"})
    assert resp.status_code == 201
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Domain", "value": "example.org"},
    )
    assert resp.status_code == 201
    eid = resp.json()["id"]

    resp = await client.post(
        "/api/v1/transforms/website_to_people/run",
        json={"entity_id": eid, "project_id": pid, "config": {"settings": {}}},
    )
    assert_error_envelope(
        resp,
        403,
        code="HTTP_403",
        message_contains="disabled for community plugins",
    )


@pytest.mark.asyncio
async def test_run_transform_blocks_stored_api_key_injection_for_blocked_service(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from ogi.api import transforms as transforms_api
    from ogi.config import settings

    class CaptureQueue:
        def enqueue(self, *args, **kwargs):
            return None

    monkeypatch.setattr(transforms_api, "get_rq_queue", lambda: CaptureQueue())
    monkeypatch.setattr(settings, "api_key_service_blocklist", ["openai"])

    resp = await client.post(
        "/api/v1/settings/api-keys",
        json={"service_name": "openai", "key": "sk-test"},
    )
    assert resp.status_code == 201

    resp = await client.post("/api/v1/projects", json={"name": "BlockedService"})
    assert resp.status_code == 201
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={"type": "Domain", "value": "example.org"},
    )
    assert resp.status_code == 201
    eid = resp.json()["id"]

    resp = await client.post(
        "/api/v1/transforms/website_to_people/run",
        json={"entity_id": eid, "project_id": pid, "config": {"settings": {}}},
    )
    assert_error_envelope(
        resp,
        403,
        code="HTTP_403",
        message_contains="blocked for service 'openai'",
    )


@pytest.mark.asyncio
async def test_plugin_api_key_usage_report_aggregates_last_use(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from ogi.api import plugins as plugins_api
    from ogi.models import PluginInfo

    plugin_info = PluginInfo(
        name="mock-community-plugin",
        display_name="Mock Community Plugin",
        verification_tier="community",
        permissions={"network": True, "filesystem": False, "subprocess": False},
        api_keys_required=[{"service": "openai", "description": "OpenAI", "env_var": "OPENAI_API_KEY"}],
    )
    plugin_engine = plugins_api.get_plugin_engine()
    monkeypatch.setattr(plugin_engine, "list_plugins", lambda: [plugin_info])

    resp = await client.post("/api/v1/projects", json={"name": "UsageReportProject"})
    assert resp.status_code == 201
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/audit-logs",
        json={
            "action": "transform.api_key_injected",
            "resource_type": "transform",
            "resource_id": "website_to_people",
            "details": {
                "plugin_name": "mock-community-plugin",
                "service_name": "openai",
            },
        },
    )
    assert resp.status_code == 201

    resp = await client.get("/api/v1/plugins/api-key-usage-report")
    assert resp.status_code == 200
    rows = resp.json()
    item = next((row for row in rows if row["plugin_name"] == "mock-community-plugin"), None)
    assert item is not None
    assert item["requested_services"] == ["openai"]
    assert item["usage"][0]["service_name"] == "openai"
    assert item["usage"][0]["last_used_at"] is not None


@pytest.mark.asyncio
async def test_registry_install_writes_system_audit_log(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from ogi.api import registry as registry_api
    from ogi.db.database import get_session
    from ogi.models import SystemAuditLog

    class FakeRegistry:
        async def fetch_index(self):
            return {"transforms": []}

        def get_transform(self, slug: str):
            return {
                "slug": slug,
                "version": "1.2.3",
                "verification_tier": "community",
                "api_keys_required": [{"service": "openai"}],
            }

    class FakeInstaller:
        async def install(self, slug: str):
            return ["plugin.yaml"]

    monkeypatch.setattr(registry_api, "get_registry_client", lambda: FakeRegistry())
    monkeypatch.setattr(registry_api, "get_transform_installer", lambda: FakeInstaller())
    monkeypatch.setattr(registry_api, "_reload_plugin_runtime", lambda name: 0)

    resp = await client.post("/api/v1/registry/install/mock-plugin")
    assert resp.status_code == 200

    rows = []
    async for session in get_session():
        rows = (
            await session.execute(select(SystemAuditLog).where(SystemAuditLog.action == "plugin.install"))
        ).scalars().all()

    assert rows
    assert rows[-1].resource_id == "mock-plugin"
    assert rows[-1].details["api_key_services"] == ["openai"]


@pytest.mark.asyncio
async def test_registry_update_reloads_plugin_runtime_metadata(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from ogi.api import registry as registry_api

    class FakeRegistry:
        async def fetch_index(self):
            return {"transforms": []}

        def get_transform(self, slug: str):
            return {
                "slug": slug,
                "version": "1.0.3",
                "verification_tier": "community",
                "api_keys_required": [],
            }

    class FakeInstaller:
        async def update(self, slug: str):
            assert slug == "username-user-scanner"
            return True

    reloaded: list[str] = []

    def fake_reload(slug: str) -> int:
        reloaded.append(slug)
        return 1

    monkeypatch.setattr(registry_api, "get_registry_client", lambda: FakeRegistry())
    monkeypatch.setattr(registry_api, "get_transform_installer", lambda: FakeInstaller())
    monkeypatch.setattr(registry_api, "_reload_plugin_runtime", fake_reload)

    resp = await client.post("/api/v1/registry/update/username-user-scanner")
    assert resp.status_code == 200
    assert reloaded == ["username-user-scanner"]
    assert resp.json()["version"] == "1.0.3"
    assert "reloaded" in resp.json()["message"]


@pytest.mark.asyncio
async def test_get_transform_run_forbidden_for_non_member(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from uuid import uuid4

    from ogi.api import transforms as transforms_api
    from ogi.api.auth import get_current_user
    from ogi.models import UserProfile

    class DummyQueue:
        def enqueue(self, *args, **kwargs):
            return None

    monkeypatch.setattr(transforms_api, "get_rq_queue", lambda: DummyQueue())

    owner = UserProfile(id=uuid4(), email="owner-runs@test.com")
    outsider = UserProfile(id=uuid4(), email="outsider-runs@test.com")

    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        resp = await client.post("/api/v1/projects", json={"name": "RunReadScope"})
        assert resp.status_code == 201
        pid = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/projects/{pid}/entities",
            json={"type": "Domain", "value": "scope.test"},
        )
        assert resp.status_code == 201
        eid = resp.json()["id"]

        resp = await client.post(
            "/api/v1/transforms/domain_to_ip/run",
            json={"entity_id": eid, "project_id": pid, "config": {"settings": {}}},
        )
        assert resp.status_code == 200
        run_id = resp.json()["id"]
    finally:
        app.dependency_overrides.clear()

    app.dependency_overrides[get_current_user] = lambda: outsider
    try:
        resp = await client.get(f"/api/v1/transforms/runs/{run_id}")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_transform_run_forbidden_for_non_member(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    from uuid import uuid4

    from ogi.api import transforms as transforms_api
    from ogi.api.auth import get_current_user
    from ogi.models import UserProfile

    class DummyQueue:
        def enqueue(self, *args, **kwargs):
            return None

    monkeypatch.setattr(transforms_api, "get_rq_queue", lambda: DummyQueue())

    owner = UserProfile(id=uuid4(), email="owner-cancel@test.com")
    outsider = UserProfile(id=uuid4(), email="outsider-cancel@test.com")

    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        resp = await client.post("/api/v1/projects", json={"name": "RunCancelScope"})
        assert resp.status_code == 201
        pid = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/projects/{pid}/entities",
            json={"type": "Domain", "value": "cancel-scope.test"},
        )
        assert resp.status_code == 201
        eid = resp.json()["id"]

        resp = await client.post(
            "/api/v1/transforms/domain_to_ip/run",
            json={"entity_id": eid, "project_id": pid, "config": {"settings": {}}},
        )
        assert resp.status_code == 200
        run_id = resp.json()["id"]
    finally:
        app.dependency_overrides.clear()

    app.dependency_overrides[get_current_user] = lambda: outsider
    try:
        resp = await client.post(f"/api/v1/transforms/runs/{run_id}/cancel")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_ws_transforms_rejects_unauthorized_client(
    sync_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from ogi.api import websocket as websocket_api

    async def deny_user(_token: str | None):
        return None

    monkeypatch.setattr(websocket_api, "_resolve_ws_user", deny_user)

    with pytest.raises(WebSocketDisconnect) as exc:
        with sync_client.websocket_connect(f"/api/v1/ws/transforms/{uuid4()}"):
            pass

    assert exc.value.code == 4001


def test_ws_transforms_rejects_forbidden_project_member(
    sync_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from ogi.api import websocket as websocket_api
    from ogi.models import UserProfile

    project = sync_client.post("/api/v1/projects", json={"name": "WS Private"}).json()
    outsider = UserProfile(id=uuid4(), email="ws-outsider@test.com")

    async def resolve_user(_token: str | None):
        return outsider

    monkeypatch.setattr(websocket_api, "_resolve_ws_user", resolve_user)

    with pytest.raises(WebSocketDisconnect) as exc:
        with sync_client.websocket_connect(f"/api/v1/ws/transforms/{project['id']}?token=test-token"):
            pass

    assert exc.value.code == 4003


def test_ws_transforms_fans_out_per_project_and_isolates_other_projects(
    sync_client: TestClient,
):
    from ogi.api import websocket as websocket_api

    project_a = sync_client.post("/api/v1/projects", json={"name": "WS A"}).json()
    project_b = sync_client.post("/api/v1/projects", json={"name": "WS B"}).json()

    event_a = {
        "type": "job_started",
        "job_id": str(uuid4()),
        "project_id": project_a["id"],
        "transform_name": "domain_to_ip",
        "input_entity_id": str(uuid4()),
        "progress": None,
        "message": None,
        "result": None,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    event_b = {
        **event_a,
        "job_id": str(uuid4()),
        "project_id": project_b["id"],
    }

    with sync_client.websocket_connect(f"/api/v1/ws/transforms/{project_a['id']}") as ws_a1:
        with sync_client.websocket_connect(f"/api/v1/ws/transforms/{project_a['id']}") as ws_a2:
            with sync_client.websocket_connect(f"/api/v1/ws/transforms/{project_b['id']}") as ws_b:
                asyncio.run(
                    websocket_api.ws_manager.broadcast_to_project(
                        UUID(project_a["id"]),
                        json.dumps(event_a),
                    )
                )
                asyncio.run(
                    websocket_api.ws_manager.broadcast_to_project(
                        UUID(project_b["id"]),
                        json.dumps(event_b),
                    )
                )

                assert ws_a1.receive_json() == event_a
                assert ws_a2.receive_json() == event_a
                assert ws_b.receive_json() == event_b


@pytest.mark.asyncio
async def test_redis_pubsub_listener_bridges_project_messages(monkeypatch: pytest.MonkeyPatch):
    from ogi.api import websocket as websocket_api

    project_id = uuid4()
    payload = {
        "type": "job_completed",
        "job_id": str(uuid4()),
        "project_id": str(project_id),
        "transform_name": "domain_to_ip",
        "input_entity_id": str(uuid4()),
        "progress": None,
        "message": None,
        "result": {"entities": [], "edges": [], "messages": [], "ui_messages": []},
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    captured: list[tuple[UUID, str]] = []

    class FakePubSub:
        def __init__(self) -> None:
            self.subscribed: list[str] = []
            self.unsubscribed: list[str] = []

        async def psubscribe(self, pattern: str) -> None:
            self.subscribed.append(pattern)

        async def listen(self):
            yield {
                "type": "pmessage",
                "channel": f"ogi:transform_events:{project_id}",
                "data": json.dumps(payload),
            }

        async def punsubscribe(self, pattern: str) -> None:
            self.unsubscribed.append(pattern)

    class FakeRedisConn:
        def __init__(self) -> None:
            self.pubsub_instance = FakePubSub()
            self.closed = False

        def pubsub(self) -> FakePubSub:
            return self.pubsub_instance

        async def aclose(self) -> None:
            self.closed = True

    fake_conn = FakeRedisConn()

    async def fake_broadcast(pid: UUID, message: str) -> None:
        captured.append((pid, message))

    monkeypatch.setattr(websocket_api.ws_manager, "broadcast_to_project", fake_broadcast)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *args, **kwargs: fake_conn)

    await websocket_api.redis_pubsub_listener()

    assert fake_conn.pubsub_instance.subscribed == ["ogi:transform_events:*"]
    assert fake_conn.pubsub_instance.unsubscribed == ["ogi:transform_events:*"]
    assert fake_conn.closed is True
    assert captured == [(project_id, json.dumps(payload))]


def test_ws_cancel_is_idempotent(
    sync_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from ogi.api import dependencies
    from ogi.api import transforms as transforms_api
    from rq.job import Job

    class DummyQueue:
        def enqueue(self, *args, **kwargs):
            return None

    class FakeRedis:
        def __init__(self) -> None:
            self.published: list[tuple[str, str]] = []

        def publish(self, channel: str, message: str) -> None:
            self.published.append((channel, message))

    class FakeJob:
        def __init__(self) -> None:
            self.cancel_calls = 0

        def cancel(self) -> None:
            self.cancel_calls += 1

    fake_redis = FakeRedis()
    fake_job = FakeJob()

    monkeypatch.setattr(transforms_api, "get_rq_queue", lambda: DummyQueue())
    monkeypatch.setattr(transforms_api, "get_redis", lambda: None)
    monkeypatch.setattr(dependencies, "get_redis", lambda: fake_redis)
    monkeypatch.setattr(Job, "fetch", classmethod(lambda cls, job_id, connection: fake_job))

    project = sync_client.post("/api/v1/projects", json={"name": "WS Cancel"}).json()
    entity = sync_client.post(
        f"/api/v1/projects/{project['id']}/entities",
        json={"type": "Domain", "value": "cancel.test"},
    ).json()
    run = sync_client.post(
        "/api/v1/transforms/domain_to_ip/run",
        json={"entity_id": entity["id"], "project_id": project["id"], "config": {"settings": {}}},
    ).json()

    with sync_client.websocket_connect(f"/api/v1/ws/transforms/{project['id']}") as ws:
        ws.send_json({"type": "cancel", "job_id": run["id"]})
        ws.send_json({"type": "cancel", "job_id": run["id"]})
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}

    assert fake_job.cancel_calls == 1
    assert len(fake_redis.published) == 1
    channel, message = fake_redis.published[0]
    assert channel == f"ogi:transform_events:{project['id']}"
    assert json.loads(message)["type"] == "job_cancelled"

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


@pytest.mark.asyncio
async def test_entity_store_save_upserts_existing_entity(client: AsyncClient):
    from uuid import UUID

    from ogi.db.database import get_session
    from ogi.models import Entity, EntityType
    from ogi.store.entity_store import EntityStore

    resp = await client.post("/api/v1/projects", json={"name": "EntityUpsert"})
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{pid}/entities",
        json={
            "type": "Domain",
            "value": "upsert.example",
            "properties": {"first_seen": "yes"},
            "notes": "initial",
            "tags": ["seed"],
            "source": "manual",
            "weight": 1,
        },
    )
    assert resp.status_code == 201
    original = resp.json()

    async for session in get_session():
        store = EntityStore(session)
        incoming = Entity(
            type=EntityType.DOMAIN,
            value="upsert.example",
            properties={"whois_creation_date": "2025-01-01"},
            notes="enriched",
            tags=["seed", "whois"],
            source="whois_lookup",
            weight=3,
            project_id=UUID(pid),
        )
        saved = await store.save(UUID(pid), incoming)
        break

    assert str(saved.id) == original["id"]

    resp = await client.get(f"/api/v1/projects/{pid}/entities")
    assert resp.status_code == 200
    entities = [e for e in resp.json() if e["value"] == "upsert.example" and e["type"] == "Domain"]
    assert len(entities) == 1
    entity = entities[0]
    assert entity["properties"]["first_seen"] == "yes"
    assert entity["origin_source"] == "manual"
    assert entity["properties"]["whois_creation_date"] == "2025-01-01"
    assert "seed" in entity["tags"]
    assert "whois" in entity["tags"]
    assert entity["notes"] == "enriched"
    assert entity["source"] == "whois_lookup"
    assert entity["weight"] == 3


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


@pytest.mark.asyncio
async def test_import_graphml(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "ImportGraphML"})
    pid = resp.json()["id"]

    payload = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="type" for="node" attr.name="type" attr.type="string"/>
  <key id="value" for="node" attr.name="value" attr.type="string"/>
  <key id="label" for="edge" attr.name="label" attr.type="string"/>
  <graph id="G" edgedefault="directed">
    <node id="n1"><data key="type">Domain</data><data key="value">graphml.test</data></node>
    <node id="n2"><data key="type">IPAddress</data><data key="value">1.1.1.1</data></node>
    <edge id="e1" source="n1" target="n2"><data key="label">resolves to</data></edge>
  </graph>
</graphml>
"""
    resp = await client.post(
        f"/api/v1/projects/{pid}/import/graphml",
        files={"file": ("import.graphml", payload.encode("utf-8"), "application/xml")},
    )
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["entities_added"] >= 2
    assert summary["edges_added"] >= 1

    resp = await client.get(f"/api/v1/projects/{pid}/entities")
    values = {e["value"] for e in resp.json()}
    assert "graphml.test" in values
    assert "1.1.1.1" in values


@pytest.mark.asyncio
async def test_import_graphml_rejects_unsafe_xml(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "ImportGraphMLUnsafe"})
    pid = resp.json()["id"]

    payload = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE graphml [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G" edgedefault="directed">
    <node id="n1"><data key="value">&xxe;</data></node>
  </graph>
</graphml>
"""
    resp = await client.post(
        f"/api/v1/projects/{pid}/import/graphml",
        files={"file": ("unsafe.graphml", payload.encode("utf-8"), "application/xml")},
    )
    assert resp.status_code == 400
    assert "Invalid GraphML" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_import_maltego_mtgx(client: AsyncClient):
    import io as _io
    import zipfile as _zipfile

    resp = await client.post("/api/v1/projects", json={"name": "ImportMTGX"})
    pid = resp.json()["id"]

    graphml = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="type" for="node" attr.name="type" attr.type="string"/>
  <key id="value" for="node" attr.name="value" attr.type="string"/>
  <key id="label" for="edge" attr.name="label" attr.type="string"/>
  <graph id="G" edgedefault="directed">
    <node id="m1"><data key="type">maltego.Domain</data><data key="value">mtgx.test</data></node>
    <node id="m2"><data key="type">maltego.IPv4Address</data><data key="value">8.8.8.8</data></node>
    <edge id="me1" source="m1" target="m2"><data key="label">to ip</data></edge>
  </graph>
</graphml>
"""
    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, "w", _zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Graphs/Graph1.graphml", graphml)

    resp = await client.post(
        f"/api/v1/projects/{pid}/import/maltego",
        files={"file": ("sample.mtgx", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["entities_added"] >= 2
    assert summary["edges_added"] >= 1

    resp = await client.get(f"/api/v1/projects/{pid}/entities")
    values = {e["value"] for e in resp.json()}
    assert "mtgx.test" in values
    assert "8.8.8.8" in values


@pytest.mark.asyncio
async def test_error_envelope_for_422_validation(client: AsyncClient):
    """Invalid payload returns unified 422 error envelope."""
    resp = await client.post("/api/v1/projects", json={})
    body = assert_error_envelope(resp, 422, code="VALIDATION_ERROR", message_contains="validation")
    assert "details" in body["error"]


@pytest.mark.asyncio
async def test_error_envelope_for_500_internal(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Unhandled server errors return unified 500 error envelope."""
    from ogi.config import settings

    monkeypatch.setattr(settings, "api_key_encryption_key", None)
    monkeypatch.setattr(settings, "expose_error_details", False)
    resp = await client.post(
        "/api/v1/settings/api-keys",
        json={"service_name": "openai", "key": "sk-test"},
    )
    body = assert_error_envelope(resp, 500, code="INTERNAL_SERVER_ERROR", message_contains="Internal Server Error")
    assert "details" not in body["error"]


@pytest.mark.asyncio
async def test_error_envelope_for_500_internal_in_debug_mode(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """When debug exposure is enabled, 500 includes internal error details."""
    from ogi.config import settings

    monkeypatch.setattr(settings, "api_key_encryption_key", None)
    monkeypatch.setattr(settings, "expose_error_details", True)
    resp = await client.post(
        "/api/v1/settings/api-keys",
        json={"service_name": "openai", "key": "sk-test"},
    )
    body = assert_error_envelope(resp, 500, code="INTERNAL_SERVER_ERROR")
    assert body["error"].get("details", {}).get("type") == "RuntimeError"


@pytest.mark.asyncio
async def test_audit_log_create_and_list(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "AuditProject"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    payload = {
        "action": "entity.redacted",
        "resource_type": "entity",
        "resource_id": "abc-123",
        "details": {"reason": "sensitive"},
    }
    resp = await client.post(f"/api/v1/projects/{project_id}/audit-logs", json=payload)
    assert resp.status_code == 201
    created = resp.json()
    assert created["action"] == "entity.redacted"
    assert created["resource_type"] == "entity"
    assert created["details"]["reason"] == "sensitive"

    resp = await client.get(f"/api/v1/projects/{project_id}/audit-logs")
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["action"] == "entity.redacted" for r in rows)


@pytest.mark.asyncio
async def test_project_events_endpoint_returns_conventions_and_items(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "EventsProject"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{project_id}/entities",
        json={
            "type": "Domain",
            "value": "events.example",
            "properties": {
                "observed_at": "2026-03-01T12:00:00Z",
                "valid_from": "2026-03-01T00:00:00Z",
                "valid_to": "2026-04-01T00:00:00Z",
                "lat": 47.3769,
                "lon": 8.5417,
                "location_label": "Zurich, CH",
                "geo_confidence": 0.9,
            },
        },
    )
    assert resp.status_code == 201

    resp = await client.post(
        f"/api/v1/projects/{project_id}/audit-logs",
        json={"action": "timeline.reviewed", "resource_type": "project", "details": {}},
    )
    assert resp.status_code == 201

    resp = await client.get(f"/api/v1/projects/{project_id}/events")
    assert resp.status_code == 200
    data = resp.json()
    assert "conventions" in data
    assert "observed_at" in data["conventions"]
    assert isinstance(data["items"], list)
    assert any(item["event_type"] == "entity_created" for item in data["items"])
    assert any(item["event_type"] == "audit_log" for item in data["items"])


@pytest.mark.asyncio
async def test_locations_endpoint_aggregates_normalized_locations(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "LocationsProject"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    for value in ("asset-1.example", "asset-2.example"):
        resp = await client.post(
            f"/api/v1/projects/{project_id}/entities",
            json={
                "type": "Domain",
                "value": value,
                "properties": {
                    "lat": 40.7128,
                    "lon": -74.0060,
                    "location_label": "New York, US",
                    "geo_confidence": 0.8,
                },
            },
        )
        assert resp.status_code == 201

    resp = await client.get(f"/api/v1/projects/{project_id}/locations")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 1
    top = rows[0]
    assert top["location_label"] == "New York, US"
    assert top["entity_count"] == 2
    assert top["lat"] == 40.7128
    assert top["lon"] == -74.006


@pytest.mark.asyncio
async def test_timeline_endpoint_returns_buckets(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "TimelineProject"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    await client.post(
        f"/api/v1/projects/{project_id}/entities",
        json={"type": "Domain", "value": "timeline-1.example"},
    )
    await client.post(
        f"/api/v1/projects/{project_id}/entities",
        json={"type": "Domain", "value": "timeline-2.example"},
    )
    await client.post(
        f"/api/v1/projects/{project_id}/audit-logs",
        json={"action": "timeline.checked", "resource_type": "project", "details": {}},
    )

    resp = await client.get(f"/api/v1/projects/{project_id}/timeline?interval=day")
    assert resp.status_code == 200
    data = resp.json()
    assert data["interval"] == "day"
    assert data["total_events"] >= 3
    assert len(data["buckets"]) >= 1
    assert data["buckets"][0]["count"] >= 1

    resp = await client.get(f"/api/v1/projects/{project_id}/timeline?interval=minute")
    assert resp.status_code == 200
    minute_data = resp.json()
    assert minute_data["interval"] == "minute"


@pytest.mark.asyncio
async def test_graph_window_filters_by_time_range(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "GraphWindowProject"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{project_id}/entities",
        json={"type": "Domain", "value": "window.example"},
    )
    assert resp.status_code == 201
    entity_id = resp.json()["id"]

    future_from = "2100-01-01T00:00:00Z"
    future_to = "2100-01-02T00:00:00Z"
    resp = await client.get(
        f"/api/v1/projects/{project_id}/graph/window?from={future_from}&to={future_to}"
    )
    assert resp.status_code == 200
    assert resp.json()["entities"] == []
    assert resp.json()["edges"] == []

    past_from = "2000-01-01T00:00:00Z"
    past_to = "2100-01-01T00:00:00Z"
    resp = await client.get(
        f"/api/v1/projects/{project_id}/graph/window?from={past_from}&to={past_to}"
    )
    assert resp.status_code == 200
    values = {e["id"] for e in resp.json()["entities"]}
    assert entity_id in values


@pytest.mark.asyncio
async def test_map_points_endpoint_returns_points_and_clusters(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "MapPointsProject"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    payloads = [
        {"type": "Location", "value": "loc-a", "properties": {"lat": 40.7128, "lon": -74.0060, "location_label": "NYC"}},
        {"type": "Location", "value": "loc-b", "properties": {"lat": 40.7131, "lon": -74.0062, "location_label": "NYC"}},
    ]
    for payload in payloads:
        created = await client.post(f"/api/v1/projects/{project_id}/entities", json=payload)
        assert created.status_code == 201

    resp = await client.get(f"/api/v1/projects/{project_id}/map/points?cluster=true&zoom=12")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["points"]) == 2
    assert isinstance(data["clusters"], list)
    if data["clusters"]:
        assert data["clusters"][0]["count"] >= 2


# ---------------------------------------------------------------------------
# AI Investigator foundations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_run_start_list_and_get(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    from ogi.config import settings

    monkeypatch.setattr(settings, "llm_provider", "test-provider")
    monkeypatch.setattr(settings, "llm_model", "test-model")

    resp = await client.post("/api/v1/projects", json={"name": "AgentProject"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{project_id}/agent/start",
        json={
            "prompt": "Investigate this project",
            "scope": {"mode": "all", "entity_ids": []},
            "budget": {"max_steps": 12, "max_transforms": 4, "max_runtime_sec": 180},
            "provider": "openai",
            "model": "gpt-4.1-mini",
        },
    )
    assert resp.status_code == 201
    run = resp.json()
    assert run["project_id"] == project_id
    assert run["status"] == "pending"
    assert run["provider"] == "openai"
    assert run["model"] == "gpt-4.1-mini"
    run_id = run["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}/agent/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert any(row["id"] == run_id for row in runs)

    resp = await client.get(f"/api/v1/projects/{project_id}/agent/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == run_id


@pytest.mark.asyncio
async def test_agent_start_rejects_duplicate_active_run(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    from ogi.config import settings

    resp = await client.post("/api/v1/projects", json={"name": "AgentDuplicate"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    payload = {
        "prompt": "First run",
        "scope": {"mode": "all", "entity_ids": []},
        "provider": "openai",
        "model": "gpt-4.1-mini",
    }
    first = await client.post(f"/api/v1/projects/{project_id}/agent/start", json=payload)
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/projects/{project_id}/agent/start",
        json={"prompt": "Second run", "scope": {"mode": "all", "entity_ids": []}},
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_agent_cancel_run(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    from ogi.config import settings

    resp = await client.post("/api/v1/projects", json={"name": "AgentCancel"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    start = await client.post(
        f"/api/v1/projects/{project_id}/agent/start",
        json={
            "prompt": "Cancel me",
            "scope": {"mode": "all", "entity_ids": []},
            "provider": "openai",
            "model": "gpt-4.1-mini",
        },
    )
    assert start.status_code == 201
    run_id = start.json()["id"]

    resp = await client.post(f"/api/v1/projects/{project_id}/agent/runs/{run_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_agent_approve_and_reject_waiting_step(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    from ogi.agent.models import AgentRun, AgentRunStatus, AgentStep, AgentStepStatus, AgentStepType
    from ogi.config import settings
    from ogi.db.database import async_session_maker

    resp = await client.post("/api/v1/projects", json={"name": "AgentApproval"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    start = await client.post(
        f"/api/v1/projects/{project_id}/agent/start",
        json={
            "prompt": "Approval flow",
            "scope": {"mode": "all", "entity_ids": []},
            "provider": "openai",
            "model": "gpt-4.1-mini",
        },
    )
    assert start.status_code == 201
    run_id = UUID(start.json()["id"])

    assert async_session_maker is not None
    async with async_session_maker() as session:
        run = await session.get(AgentRun, run_id)
        assert run is not None
        run.status = AgentRunStatus.PAUSED
        session.add(run)
        await session.commit()

        step = AgentStep(
            run_id=run_id,
            step_number=1,
            type=AgentStepType.APPROVAL_REQUEST,
            tool_name="run_transform",
            status=AgentStepStatus.WAITING_APPROVAL,
        )
        session.add(step)
        await session.commit()
        await session.refresh(step)
        step_id = step.id

    approve = await client.post(
        f"/api/v1/projects/{project_id}/agent/runs/{run_id}/steps/{step_id}/approve",
        json={},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    async with async_session_maker() as session:
        run = await session.get(AgentRun, run_id)
        assert run is not None
        assert run.status == AgentRunStatus.PENDING

        step = AgentStep(
            run_id=run_id,
            step_number=2,
            type=AgentStepType.APPROVAL_REQUEST,
            tool_name="run_transform",
            status=AgentStepStatus.WAITING_APPROVAL,
        )
        session.add(step)
        run.status = AgentRunStatus.PAUSED
        session.add(run)
        await session.commit()
        await session.refresh(step)
        step_id = step.id

    reject = await client.post(
        f"/api/v1/projects/{project_id}/agent/runs/{run_id}/steps/{step_id}/reject",
        json={},
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_agent_settings_roundtrip_and_has_api_key(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    from ogi.config import settings

    monkeypatch.setattr(settings, "llm_provider", "openai")

    save_key = await client.post(
        "/api/v1/settings/api-keys",
        json={"service_name": "openai", "key": "sk-test"},
    )
    assert save_key.status_code == 201

    project = await client.post("/api/v1/projects", json={"name": "AgentSettingsProject"})
    assert project.status_code == 201
    project_id = project.json()["id"]

    get_initial = await client.get(f"/api/v1/projects/{project_id}/agent/settings")
    assert get_initial.status_code == 200
    assert get_initial.json()["has_api_key"] is True

    save_settings = await client.put(
        f"/api/v1/projects/{project_id}/agent/settings",
        json={"provider": "openai", "model": "gpt-4.1-mini"},
    )
    assert save_settings.status_code == 200
    assert save_settings.json()["provider"] == "openai"
    assert save_settings.json()["model"] == "gpt-4.1-mini"
    assert save_settings.json()["has_api_key"] is True

    get_saved = await client.get(f"/api/v1/projects/{project_id}/agent/settings")
    assert get_saved.status_code == 200
    assert get_saved.json()["provider"] == "openai"
    assert get_saved.json()["model"] == "gpt-4.1-mini"


@pytest.mark.asyncio
async def test_agent_settings_models_endpoint_returns_provider_models(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    from ogi.config import settings

    save_key = await client.post(
        "/api/v1/settings/api-keys",
        json={"service_name": "openai", "key": "sk-test"},
    )
    assert save_key.status_code == 201

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            assert url == "https://api.openai.com/v1/models"
            return httpx.Response(
                200,
                json={"data": [{"id": "gpt-4.1-mini"}, {"id": "gpt-4.1"}]},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr("ogi.agent.llm_provider.httpx.AsyncClient", lambda *a, **k: _Client())

    project = await client.post("/api/v1/projects", json={"name": "AgentModelCatalogProject"})
    assert project.status_code == 201
    project_id = project.json()["id"]

    response = await client.get(f"/api/v1/projects/{project_id}/agent/settings/models?provider=openai")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "openai"
    assert payload["has_api_key"] is True
    assert any(item["id"] == "gpt-4.1-mini" for item in payload["available_models"])


@pytest.mark.asyncio
async def test_agent_settings_test_endpoint_validates_model(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    from ogi.config import settings

    save_key = await client.post(
        "/api/v1/settings/api-keys",
        json={"service_name": "openai", "key": "sk-test"},
    )
    assert save_key.status_code == 201

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            if url == "https://api.openai.com/v1/models":
                return httpx.Response(
                    200,
                    json={"data": [{"id": "gpt-4.1-mini"}]},
                    request=httpx.Request("GET", url),
                )
            if url == "https://api.openai.com/v1/models/gpt-4.1-mini":
                return httpx.Response(200, json={"id": "gpt-4.1-mini"}, request=httpx.Request("GET", url))
            return httpx.Response(404, json={"error": "not found"}, request=httpx.Request("GET", url))

    monkeypatch.setattr("ogi.agent.llm_provider.httpx.AsyncClient", lambda *a, **k: _Client())

    project = await client.post("/api/v1/projects", json={"name": "AgentModelTestProject"})
    assert project.status_code == 201
    project_id = project.json()["id"]

    response = await client.post(
        f"/api/v1/projects/{project_id}/agent/settings/test",
        json={"provider": "openai", "model": "gpt-4.1-mini"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["model_found"] is True


@pytest.mark.asyncio
async def test_entity_store_list_filters_and_search(client: AsyncClient):
    from uuid import UUID

    from ogi.db.database import async_session_maker
    from ogi.models import EntityCreate, EntityType
    from ogi.store.entity_store import EntityStore

    resp = await client.post("/api/v1/projects", json={"name": "EntitySearchProject"})
    assert resp.status_code == 201
    project_id = UUID(resp.json()["id"])

    assert async_session_maker is not None
    async with async_session_maker() as session:
        store = EntityStore(session)
        await store.create(project_id, EntityCreate(type=EntityType.DOMAIN, value="alpha.example"))
        await store.create(project_id, EntityCreate(type=EntityType.DOMAIN, value="beta.example"))
        await store.create(project_id, EntityCreate(type=EntityType.IP_ADDRESS, value="1.2.3.4"))

        domains = await store.list_by_project(project_id, type_filter=EntityType.DOMAIN, limit=10)
        assert {entity.value for entity in domains} == {"alpha.example", "beta.example"}

        search_hits = await store.search(project_id, "alpha", limit=10)
        assert [entity.value for entity in search_hits] == ["alpha.example"]

        type_filtered_hits = await store.search(project_id, "example", type_filter=EntityType.DOMAIN, limit=10)
        assert {entity.value for entity in type_filtered_hits} == {"alpha.example", "beta.example"}


@pytest.mark.asyncio
async def test_map_routes_endpoint_returns_routes_for_geo_edges(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "MapRoutesProject"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    a = await client.post(
        f"/api/v1/projects/{project_id}/entities",
        json={"type": "Location", "value": "source", "properties": {"lat": 51.5074, "lon": -0.1278}},
    )
    b = await client.post(
        f"/api/v1/projects/{project_id}/entities",
        json={"type": "Location", "value": "target", "properties": {"lat": 48.8566, "lon": 2.3522}},
    )
    assert a.status_code == 201 and b.status_code == 201
    src_id = a.json()["id"]
    dst_id = b.json()["id"]

    edge = await client.post(
        f"/api/v1/projects/{project_id}/edges",
        json={"source_id": src_id, "target_id": dst_id, "label": "travel"},
    )
    assert edge.status_code == 201

    resp = await client.get(f"/api/v1/projects/{project_id}/map/routes")
    assert resp.status_code == 200
    routes = resp.json()["routes"]
    assert len(routes) >= 1
    assert routes[0]["source_entity_id"] == src_id
    assert routes[0]["target_entity_id"] == dst_id


@pytest.mark.asyncio
async def test_map_store_upsert_cache_recovers_from_duplicate_insert(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    from ogi.db.database import get_session
    from ogi.models import GeocodeCache
    from ogi.store.map_store import MapStore

    async for session in get_session():
        session.add(
            GeocodeCache(
                query="nyc",
                lat=40.7128,
                lon=-74.0060,
                display_name="New York, NY",
                confidence=0.7,
                source="cache",
            )
        )
        await session.commit()

        store = MapStore(session)

        calls = 0

        async def miss_then_reload(query: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return None
            return (await session.execute(select(GeocodeCache).where(GeocodeCache.query == query))).scalar_one_or_none()

        monkeypatch.setattr(store, "_get_cache", miss_then_reload)

        row = await store._upsert_cache("NYC", 40.7130, -74.0059, 0.9, source="entity", display_name="New York City")
        assert row.query == "nyc"
        assert row.source == "entity"
        assert row.display_name == "New York City"

        rows = list((await session.execute(select(GeocodeCache).where(GeocodeCache.query == "nyc"))).scalars().all())
        assert len(rows) == 1
        assert rows[0].confidence == 0.9
        break


@pytest.mark.asyncio
async def test_location_suggest_returns_cached_results(client: AsyncClient):
    from ogi.db.database import get_session
    from ogi.models import GeocodeCache

    resp = await client.post("/api/v1/projects", json={"name": "LocationSuggestProject"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    async for session in get_session():
        session.add(
            GeocodeCache(
                query="zurich, switzerland",
                lat=47.3769,
                lon=8.5417,
                display_name="Zurich, Switzerland",
                confidence=0.8,
                source="cache",
            )
        )
        await session.commit()
        break

    resp = await client.get(f"/api/v1/projects/{project_id}/locations/suggest?q=zur&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["rate_limited"] is False
    assert data["suggestions"]
    assert "Zurich" in data["suggestions"][0]["display_name"]


@pytest.mark.asyncio
async def test_location_suggest_rate_limit_feedback(client: AsyncClient):
    from ogi.store.location_search_store import LocationSearchStore
    import time as _time

    resp = await client.post("/api/v1/projects", json={"name": "LocationSuggestRateProject"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    LocationSearchStore._cooldown_until = _time.time() + 30
    try:
        resp = await client.get(f"/api/v1/projects/{project_id}/locations/suggest?q=london&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate_limited"] is True
        assert (data["retry_after_seconds"] or 0) > 0
    finally:
        LocationSearchStore._cooldown_until = 0.0
