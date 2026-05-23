import json
from datetime import datetime, timezone
from typing import Any

from ogi.models import Entity, EntityType
from ogi.transforms.base import TransformConfig

POSITIVE_STATUSES = {
    "claimed",
    "exists",
    "found",
    "registered",
    "taken",
    "valid",
    "success",
    "true",
}

NEGATIVE_STATUSES = {
    "available",
    "false",
    "missing",
    "not found",
    "not_found",
    "unknown",
}


def load_fixture_payload(config: TransformConfig) -> tuple[Any | None, str | None]:
    raw = config.settings.get("result_json", "").strip()
    if not raw:
        return None, "No result_json fixture was provided."
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        return None, f"Invalid result_json fixture: {exc}"


def source_timestamp(config: TransformConfig) -> str:
    configured = config.settings.get("source_timestamp", "").strip()
    if configured:
        return configured
    return datetime.now(timezone.utc).isoformat()


def result_items(payload: Any) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(payload, dict):
        nested = payload.get("results")
        if isinstance(nested, dict):
            return [
                (str(key), value)
                for key, value in nested.items()
                if isinstance(value, dict)
            ]
        return [
            (str(key), value)
            for key, value in payload.items()
            if isinstance(value, dict)
        ]
    if isinstance(payload, list):
        items: list[tuple[str, dict[str, Any]]] = []
        for index, value in enumerate(payload):
            if isinstance(value, dict):
                name = first_present(value, ["name", "site", "service", "platform"], str(index))
                items.append((str(name), value))
        return items
    return []


def first_present(record: dict[str, Any], keys: list[str], default: Any = "") -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None and value != "":
            return value
    return default


def is_positive_match(record: dict[str, Any]) -> bool:
    for key in ["exists", "found", "registered", "claimed", "valid"]:
        value = record.get(key)
        if isinstance(value, bool):
            return value
    status = str(first_present(record, ["status", "state", "result"], "")).strip().lower()
    if status in NEGATIVE_STATUSES:
        return False
    if status in POSITIVE_STATUSES:
        return True
    return False


def provenance_properties(
    *,
    tool_name: str,
    command: str,
    source_timestamp: str,
    confidence: float,
    warning: str,
    tool_version: str = "",
    raw_match_url: str | None = "",
    raw_record: Any | None = None,
) -> dict[str, Any]:
    props: dict[str, Any] = {
        "tool_name": tool_name,
        "tool_version": tool_version,
        "command": command,
        "confidence": confidence,
        "raw_match_url": raw_match_url or "",
        "source_timestamp": source_timestamp,
        "warning": warning,
    }
    if raw_record is not None:
        props["raw_record"] = raw_record
    return props


def fixture_document(
    *,
    tool_name: str,
    subject: str,
    match_count: int,
    properties: dict[str, Any],
    source: str,
) -> Entity:
    suffix = "match" if match_count == 1 else "matches"
    return Entity(
        type=EntityType.DOCUMENT,
        value=f"{tool_name} evidence for {subject}: {match_count} {suffix}",
        properties=properties | {
            "subject": subject,
            "match_count": match_count,
            "document_type": "user_osint_tool_fixture",
        },
        source=source,
    )
