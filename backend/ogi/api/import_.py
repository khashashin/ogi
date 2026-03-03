import csv
import io
import json
import zipfile
from typing import Any
from uuid import UUID
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from ogi.models import Entity, EntityType, EdgeCreate
from ogi.api.auth import require_project_editor
from ogi.api.dependencies import get_entity_store, get_edge_store, get_graph_engine
from ogi.store.entity_store import EntityStore
from ogi.store.edge_store import EdgeStore

router = APIRouter(prefix="/projects/{project_id}/import", tags=["import"])


class ImportSummary(BaseModel):
    entities_added: int = 0
    entities_merged: int = 0
    entities_skipped: int = 0
    edges_added: int = 0
    edges_skipped: int = 0


def _normalize_entity_type(raw: str | None) -> EntityType:
    value = (raw or "").strip()
    if not value:
        return EntityType.DOCUMENT

    if value in {member.value for member in EntityType}:
        return EntityType(value)

    lowered = value.lower()
    maltego_map = {
        "maltego.domain": EntityType.DOMAIN,
        "maltego.dnsname": EntityType.DOMAIN,
        "maltego.ipv4address": EntityType.IP_ADDRESS,
        "maltego.ipaddress": EntityType.IP_ADDRESS,
        "maltego.url": EntityType.URL,
        "maltego.emailaddress": EntityType.EMAIL_ADDRESS,
        "maltego.email": EntityType.EMAIL_ADDRESS,
        "maltego.person": EntityType.PERSON,
        "maltego.organization": EntityType.ORGANIZATION,
        "maltego.location": EntityType.LOCATION,
        "maltego.phonenumber": EntityType.PHONE_NUMBER,
    }
    return maltego_map.get(lowered, EntityType.DOCUMENT)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _parse_graphml(content: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid GraphML: {exc}") from exc

    key_meta: dict[str, tuple[str, str]] = {}
    for elem in root.iter():
        if _local_name(elem.tag) != "key":
            continue
        key_id = elem.attrib.get("id")
        if not key_id:
            continue
        attr_name = elem.attrib.get("attr.name", key_id)
        attr_for = elem.attrib.get("for", "")
        key_meta[key_id] = (attr_name, attr_for)

    entities_payload: list[dict[str, Any]] = []
    edges_payload: list[dict[str, Any]] = []

    for elem in root.iter():
        tag = _local_name(elem.tag)
        if tag == "node":
            data_map: dict[str, str] = {}
            for data_elem in elem:
                if _local_name(data_elem.tag) != "data":
                    continue
                key_id = data_elem.attrib.get("key", "")
                key_name = key_meta.get(key_id, (key_id, ""))[0]
                data_map[key_name] = (data_elem.text or "").strip()

            raw_type = data_map.get("type") or data_map.get("entity_type")
            entity_type = _normalize_entity_type(raw_type)
            value = data_map.get("value") or elem.attrib.get("id", "").strip()
            if not value:
                continue

            properties: dict[str, Any] = {}
            for key, val in data_map.items():
                if key in {"type", "entity_type", "value", "label", "weight"}:
                    continue
                properties[key] = val
            if raw_type and raw_type.lower().startswith("maltego."):
                properties.setdefault("original_type", raw_type)

            payload: dict[str, Any] = {
                "import_id": elem.attrib.get("id", ""),
                "type": entity_type.value,
                "value": value,
                "properties": properties,
                "source": "graphml_import",
            }
            raw_weight = data_map.get("weight")
            if raw_weight and raw_weight.isdigit():
                payload["weight"] = int(raw_weight)
            entities_payload.append(payload)

        elif tag == "edge":
            data_map: dict[str, str] = {}
            for data_elem in elem:
                if _local_name(data_elem.tag) != "data":
                    continue
                key_id = data_elem.attrib.get("key", "")
                key_name = key_meta.get(key_id, (key_id, ""))[0]
                data_map[key_name] = (data_elem.text or "").strip()

            label = data_map.get("label") or data_map.get("edge_label") or ""
            edges_payload.append({
                "source_import_id": elem.attrib.get("source", ""),
                "target_import_id": elem.attrib.get("target", ""),
                "label": label,
                "source_transform": "graphml_import",
            })

    return entities_payload, edges_payload


def _extract_mtgx_graphml(content: bytes) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            candidates = [
                name for name in archive.namelist()
                if name.lower().endswith(".graphml")
            ]
            if not candidates:
                raise HTTPException(status_code=400, detail="MTGX archive does not contain a GraphML file")
            preferred = next(
                (name for name in candidates if name.lower().endswith("graphs/graph1.graphml")),
                candidates[0],
            )
            return archive.read(preferred)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid MTGX archive") from exc


async def _import_entities_and_edges(
    project_id: UUID,
    entities_payload: list[dict[str, Any]],
    edges_payload: list[dict[str, Any]],
    es: EntityStore,
    edge_s: EdgeStore,
    entity_source_fallback: str,
    edge_source_fallback: str,
) -> ImportSummary:
    summary = ImportSummary()
    graph = get_graph_engine(project_id)
    id_map: dict[str, UUID] = {}

    for entity_data in entities_payload:
        try:
            value = str(entity_data.get("value", "")).strip()
            if not value:
                summary.entities_skipped += 1
                continue

            raw_type = str(entity_data.get("type", ""))
            entity_type = _normalize_entity_type(raw_type)
            existing = await es.find_by_type_and_value(project_id, entity_type, value)

            entity = Entity(
                type=entity_type,
                value=value,
                properties=entity_data.get("properties", {}) or {},
                notes=str(entity_data.get("notes", "") or ""),
                tags=entity_data.get("tags", []) or [],
                source=str(entity_data.get("source", entity_source_fallback) or entity_source_fallback),
                weight=int(entity_data.get("weight", 1) or 1),
                project_id=project_id,
            )
            saved = await es.save(project_id, entity)
            import_id = str(entity_data.get("import_id", "")).strip() or str(entity_data.get("id", "")).strip()
            if import_id:
                id_map[import_id] = saved.id
            if existing is None:
                summary.entities_added += 1
            else:
                summary.entities_merged += 1

            if not graph.get_entity(saved.id):
                graph.add_entity(saved)
        except Exception:
            summary.entities_skipped += 1

    for edge_data in edges_payload:
        try:
            source_key = str(edge_data.get("source_import_id", "")).strip() or str(edge_data.get("source_id", "")).strip()
            target_key = str(edge_data.get("target_import_id", "")).strip() or str(edge_data.get("target_id", "")).strip()
            actual_source = id_map.get(source_key)
            actual_target = id_map.get(target_key)
            if not actual_source or not actual_target:
                summary.edges_skipped += 1
                continue

            edge_create = EdgeCreate(
                source_id=actual_source,
                target_id=actual_target,
                label=str(edge_data.get("label", "")),
                source_transform=str(edge_data.get("source_transform", edge_source_fallback)),
            )
            saved_edge = await edge_s.create(project_id, edge_create)
            try:
                graph.add_edge(saved_edge)
            except ValueError:
                pass
            summary.edges_added += 1
        except Exception:
            summary.edges_skipped += 1

    return summary


@router.post("/json", response_model=ImportSummary)
async def import_json(
    project_id: UUID,
    file: UploadFile = File(...),
    _role: str = Depends(require_project_editor),
    es: EntityStore = Depends(get_entity_store),
    edge_s: EdgeStore = Depends(get_edge_store),
) -> ImportSummary:
    content = await file.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    if "entities" not in data or "edges" not in data:
        raise HTTPException(status_code=400, detail="JSON must contain 'entities' and 'edges' arrays")

    entities_payload = []
    for entity_data in data["entities"]:
        if isinstance(entity_data, dict):
            payload = dict(entity_data)
            payload.setdefault("import_id", str(entity_data.get("id", "")))
            entities_payload.append(payload)

    edges_payload = []
    for edge_data in data["edges"]:
        if isinstance(edge_data, dict):
            payload = dict(edge_data)
            payload.setdefault("source_import_id", str(edge_data.get("source_id", "")))
            payload.setdefault("target_import_id", str(edge_data.get("target_id", "")))
            edges_payload.append(payload)

    return await _import_entities_and_edges(
        project_id,
        entities_payload,
        edges_payload,
        es,
        edge_s,
        entity_source_fallback="import",
        edge_source_fallback="import",
    )


@router.post("/csv", response_model=ImportSummary)
async def import_csv(
    project_id: UUID,
    file: UploadFile = File(...),
    _role: str = Depends(require_project_editor),
    es: EntityStore = Depends(get_entity_store),
) -> ImportSummary:
    """Import entities from a CSV file. Expected columns: type, value, properties (JSON), weight, notes, tags, source"""
    content = (await file.read()).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    summary = ImportSummary()
    graph = get_graph_engine(project_id)

    for row in reader:
        try:
            entity_type = EntityType(row.get("type", ""))
            value = row.get("value", "").strip()
            if not value:
                summary.entities_skipped += 1
                continue

            properties = json.loads(row.get("properties", "{}"))
            weight = int(row.get("weight", "1"))
            notes = row.get("notes", "")
            tags_str = row.get("tags", "")
            tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
            source = row.get("source", "csv_import")

            entity = Entity(
                type=entity_type,
                value=value,
                properties=properties,
                weight=weight,
                notes=notes,
                tags=tags,
                source=source,
            )
            saved = await es.save(project_id, entity)
            if saved.id == entity.id:
                summary.entities_added += 1
            else:
                summary.entities_merged += 1
            if not graph.get_entity(saved.id):
                graph.add_entity(saved)
        except Exception:
            summary.entities_skipped += 1

    return summary


@router.post("/graphml", response_model=ImportSummary)
async def import_graphml(
    project_id: UUID,
    file: UploadFile = File(...),
    _role: str = Depends(require_project_editor),
    es: EntityStore = Depends(get_entity_store),
    edge_s: EdgeStore = Depends(get_edge_store),
) -> ImportSummary:
    content = await file.read()
    entities_payload, edges_payload = _parse_graphml(content)
    return await _import_entities_and_edges(
        project_id,
        entities_payload,
        edges_payload,
        es,
        edge_s,
        entity_source_fallback="graphml_import",
        edge_source_fallback="graphml_import",
    )


@router.post("/maltego", response_model=ImportSummary)
async def import_maltego(
    project_id: UUID,
    file: UploadFile = File(...),
    _role: str = Depends(require_project_editor),
    es: EntityStore = Depends(get_entity_store),
    edge_s: EdgeStore = Depends(get_edge_store),
) -> ImportSummary:
    content = await file.read()
    graphml = _extract_mtgx_graphml(content)
    entities_payload, edges_payload = _parse_graphml(graphml)
    for entity_payload in entities_payload:
        entity_payload["source"] = "maltego_import"
    for edge_payload in edges_payload:
        edge_payload["source_transform"] = "maltego_import"
    return await _import_entities_and_edges(
        project_id,
        entities_payload,
        edges_payload,
        es,
        edge_s,
        entity_source_fallback="maltego_import",
        edge_source_fallback="maltego_import",
    )
