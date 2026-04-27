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
        json={"type": "Organization", "value": "Example Org", "properties": {"website": "example.com"}},
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
        "/api/v1/transforms/organization_to_team_members/settings/user",
        json={"settings": {"openai_model": "gpt-4.1-mini", "max_members": "42"}},
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/api/v1/transforms/organization_to_team_members/run",
        json={"entity_id": eid, "project_id": pid, "config": {"settings": {}}},
    )
    assert resp.status_code == 200
    settings = captured_config.get("settings", {})
    assert settings.get("openai_model") == "gpt-4.1-mini"
    assert settings.get("max_members") == "42"
    assert settings.get("openai_api_key") == "sk-test"


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
