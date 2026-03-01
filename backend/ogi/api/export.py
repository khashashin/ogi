import csv
import io
import json
import zipfile
from uuid import UUID
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from ogi.models import UserProfile
from ogi.api.auth import get_current_user, require_project_viewer
from ogi.api.dependencies import get_entity_store, get_edge_store, get_project_store
from ogi.store.project_store import ProjectStore
from ogi.store.entity_store import EntityStore
from ogi.store.edge_store import EdgeStore
from ogi.config import settings

router = APIRouter(prefix="/projects/{project_id}/export", tags=["export"])


def _get_supabase_storage():  # type: ignore[no-untyped-def]
    """Return Supabase storage client or None if not configured."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None
    try:
        from supabase import create_client
        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        return client.storage
    except Exception:
        return None


async def _upload_to_storage(
    project_id: UUID, filename: str, content: bytes, content_type: str,
) -> str | None:
    """Upload content to Supabase Storage, return signed URL or None."""
    storage = _get_supabase_storage()
    if storage is None:
        return None
    try:
        path = f"{project_id}/{filename}"
        storage.from_("exports").upload(path, content, {"content-type": content_type})
        signed = storage.from_("exports").create_signed_url(path, 3600)
        return signed.get("signedURL") or signed.get("signedUrl")
    except Exception:
        return None


@router.get("/json")
async def export_json(
    project_id: UUID,
    role: str = Depends(require_project_viewer),
    current_user: UserProfile = Depends(get_current_user),
    cloud: bool = Query(False, description="Upload to Supabase Storage"),
    project_store: ProjectStore = Depends(get_project_store),
    entity_store: EntityStore = Depends(get_entity_store),
    edge_store: EdgeStore = Depends(get_edge_store),
) -> Response:

    project = await project_store.get(project_id)
    entities = await entity_store.list_by_project(project_id)
    edges = await edge_store.list_by_project(project_id)

    data = {
        "version": "1.0",
        "project": {
            "name": project.name if project else "",
            "description": project.description if project else "",
        },
        "entities": [e.model_dump(mode="json") for e in entities],
        "edges": [e.model_dump(mode="json") for e in edges],
    }

    content = json.dumps(data, indent=2, default=str)
    filename = f"{project.name if project else 'export'}.ogi.json"

    if cloud:
        url = await _upload_to_storage(
            project_id, filename, content.encode(), "application/json"
        )
        if url:
            return Response(
                content=json.dumps({"url": url}),
                media_type="application/json",
            )

    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/csv")
async def export_csv(
    project_id: UUID,
    role: str = Depends(require_project_viewer),
    current_user: UserProfile = Depends(get_current_user),
    cloud: bool = Query(False, description="Upload to Supabase Storage"),
    project_store: ProjectStore = Depends(get_project_store),
    entity_store: EntityStore = Depends(get_entity_store),
    edge_store: EdgeStore = Depends(get_edge_store),
) -> Response:

    project = await project_store.get(project_id)
    entities = await entity_store.list_by_project(project_id)
    edges = await edge_store.list_by_project(project_id)

    # Create zip with two CSVs
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Entities CSV
        entity_buf = io.StringIO()
        writer = csv.writer(entity_buf)
        writer.writerow(["id", "type", "value", "properties", "weight", "notes", "tags", "source", "created_at"])
        for e in entities:
            writer.writerow([
                str(e.id), e.type.value, e.value,
                json.dumps(e.properties), e.weight, e.notes,
                ",".join(e.tags), e.source, e.created_at.isoformat(),
            ])
        zf.writestr("entities.csv", entity_buf.getvalue())

        # Edges CSV
        edge_buf = io.StringIO()
        writer = csv.writer(edge_buf)
        writer.writerow(["id", "source_id", "target_id", "label", "weight", "source_transform", "created_at"])
        for e in edges:
            writer.writerow([
                str(e.id), str(e.source_id), str(e.target_id),
                e.label, e.weight, e.source_transform, e.created_at.isoformat(),
            ])
        zf.writestr("edges.csv", edge_buf.getvalue())

    filename = f"{project.name if project else 'export'}.csv.zip"
    zip_bytes = zip_buffer.getvalue()

    if cloud:
        url = await _upload_to_storage(
            project_id, filename, zip_bytes, "application/zip"
        )
        if url:
            return Response(
                content=json.dumps({"url": url}),
                media_type="application/json",
            )

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/graphml")
async def export_graphml(
    project_id: UUID,
    role: str = Depends(require_project_viewer),
    current_user: UserProfile = Depends(get_current_user),
    cloud: bool = Query(False, description="Upload to Supabase Storage"),
    entity_store: EntityStore = Depends(get_entity_store),
    edge_store: EdgeStore = Depends(get_edge_store),
) -> Response:

    entities = await entity_store.list_by_project(project_id)
    edges = await edge_store.list_by_project(project_id)

    ns = "http://graphml.graphstudio.org"
    graphml = Element("graphml", xmlns=ns)

    # Attribute declarations
    for attr_name, attr_type, attr_for in [
        ("type", "string", "node"),
        ("value", "string", "node"),
        ("weight", "int", "node"),
        ("source_field", "string", "node"),
        ("label", "string", "edge"),
        ("edge_weight", "int", "edge"),
    ]:
        key = SubElement(graphml, "key")
        key.set("id", attr_name)
        key.set("for", attr_for)
        key.set("attr.name", attr_name)
        key.set("attr.type", attr_type)

    graph_el = SubElement(graphml, "graph")
    graph_el.set("id", "G")
    graph_el.set("edgedefault", "directed")

    for entity in entities:
        node = SubElement(graph_el, "node", id=str(entity.id))
        for key, val in [
            ("type", entity.type.value),
            ("value", entity.value),
            ("weight", str(entity.weight)),
            ("source_field", entity.source),
        ]:
            data = SubElement(node, "data", key=key)
            data.text = val

    for edge in edges:
        edge_el = SubElement(
            graph_el, "edge",
            id=str(edge.id),
            source=str(edge.source_id),
            target=str(edge.target_id),
        )
        label_data = SubElement(edge_el, "data", key="label")
        label_data.text = edge.label
        weight_data = SubElement(edge_el, "data", key="edge_weight")
        weight_data.text = str(edge.weight)

    content = tostring(graphml, encoding="unicode", xml_declaration=True)
    filename = "export.graphml"

    if cloud:
        url = await _upload_to_storage(
            project_id, filename, content.encode(), "application/xml"
        )
        if url:
            return Response(
                content=json.dumps({"url": url}),
                media_type="application/json",
            )

    return Response(
        content=content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
