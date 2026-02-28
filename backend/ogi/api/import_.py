import csv
import io
import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from ogi.models import Entity, EntityType, Edge, EdgeCreate
from ogi.api.dependencies import get_entity_store, get_edge_store, get_graph_engine

router = APIRouter(prefix="/projects/{project_id}/import", tags=["import"])


class ImportSummary(BaseModel):
    entities_added: int = 0
    entities_merged: int = 0
    entities_skipped: int = 0
    edges_added: int = 0
    edges_skipped: int = 0


@router.post("/json", response_model=ImportSummary)
async def import_json(project_id: UUID, file: UploadFile = File(...)) -> ImportSummary:
    content = await file.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    if "entities" not in data or "edges" not in data:
        raise HTTPException(status_code=400, detail="JSON must contain 'entities' and 'edges' arrays")

    summary = ImportSummary()
    es = get_entity_store()
    edge_s = get_edge_store()
    graph = get_graph_engine(project_id)

    # Map import IDs to persisted IDs
    id_map: dict[str, UUID] = {}

    for entity_data in data["entities"]:
        try:
            entity = Entity(**entity_data)
            saved = await es.save(project_id, entity)
            id_map[str(entity.id)] = saved.id
            if saved.id == entity.id:
                summary.entities_added += 1
            else:
                summary.entities_merged += 1
            if not graph.get_entity(saved.id):
                graph.add_entity(saved)
        except Exception:
            summary.entities_skipped += 1

    for edge_data in data["edges"]:
        try:
            source_str = str(edge_data.get("source_id", ""))
            target_str = str(edge_data.get("target_id", ""))
            actual_source = id_map.get(source_str)
            actual_target = id_map.get(target_str)
            if not actual_source or not actual_target:
                summary.edges_skipped += 1
                continue

            edge_create = EdgeCreate(
                source_id=actual_source,
                target_id=actual_target,
                label=edge_data.get("label", ""),
                source_transform=edge_data.get("source_transform", "import"),
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


@router.post("/csv", response_model=ImportSummary)
async def import_csv(project_id: UUID, file: UploadFile = File(...)) -> ImportSummary:
    """Import entities from a CSV file. Expected columns: type, value, properties (JSON), weight, notes, tags, source"""
    content = (await file.read()).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    summary = ImportSummary()
    es = get_entity_store()
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
