import hashlib
import json
from typing import Any

from ogi.models import Edge, Entity, EntityType, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig, TransformSetting
from ogi.transforms.user_osint import load_fixture_payload, source_timestamp


PROVIDER_NAME = "Breach.vip"
PROVIDER_URL = "https://breach.vip/"
BOUNDARY = (
    "Summary-only Breach.vip fixture import. Do not paste raw breach rows, passwords, "
    "credential hashes, cookies, sessions, raw provider exports, or infostealer material."
)
SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "passwords",
    "credential_hash",
    "credential_hashes",
    "hash",
    "raw_records",
    "raw_rows",
    "raw_secret",
    "cookies",
    "sessions",
    "tokens",
}


def _summary_counts(payload: dict[str, Any]) -> dict[str, Any]:
    counts = payload.get("summary_counts")
    if isinstance(counts, dict):
        return counts
    return {
        "breach_count": payload.get("breach_count", 0),
        "alias_hit_count": payload.get("alias_hit_count", 0),
        "paste_count": payload.get("paste_count", 0),
        "stealer_log_count": payload.get("stealer_log_count", 0),
    }


def _dataset_ids(payload: dict[str, Any]) -> list[str]:
    values = payload.get("dataset_ids", [])
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value).strip()]


def _warnings(payload: dict[str, Any]) -> list[str]:
    values = payload.get("warnings", [])
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value).strip()]


def _excluded_sensitive_material(payload: dict[str, Any]) -> list[str]:
    return sorted(key for key in SENSITIVE_KEYS if key in payload)


def _safe_payload_sha256(payload: dict[str, Any]) -> str:
    safe = {key: value for key, value in payload.items() if key not in SENSITIVE_KEYS}
    return hashlib.sha256(
        json.dumps(safe, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


class _BreachVipSummaryTransform(BaseTransform):
    category = "People"
    output_types = [EntityType.DOCUMENT, EntityType.IDENTIFIER]
    settings = [
        TransformSetting(
            name="result_json",
            display_name="Breach.vip Summary JSON",
            description=(
                "Saved summary-only Breach.vip result JSON. Do not paste raw rows, passwords, "
                "hashes, cookies, sessions, or provider exports."
            ),
            default="",
            field_type="string",
        ),
        TransformSetting(
            name="source_timestamp",
            display_name="Source Timestamp",
            description="Timestamp for the reviewed provider summary.",
            default="",
            field_type="string",
        ),
    ]
    document_type = "provider_exposure_summary"
    query_type = ""

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        payload, error = load_fixture_payload(config)
        if error:
            return TransformResult(messages=[error, "Paste reviewed summary-only Breach.vip JSON output."])
        if not isinstance(payload, dict):
            return TransformResult(messages=["Breach.vip fixture must be a JSON object."])

        timestamp = source_timestamp(config)
        subject = entity.value.strip()
        summary_counts = _summary_counts(payload)
        dataset_ids = _dataset_ids(payload)
        excluded = _excluded_sensitive_material(payload)
        result_status = str(payload.get("result_status", payload.get("status", "")))
        warnings = _warnings(payload)
        safe_sha256 = _safe_payload_sha256(payload)
        common_props: dict[str, Any] = {
            "provider_name": PROVIDER_NAME,
            "provider_url": PROVIDER_URL,
            "query": subject,
            "query_type": self.query_type,
            "result_status": result_status,
            "summary_counts": summary_counts,
            "summary_only": True,
            "dataset_ids": dataset_ids,
            "source_timestamp": timestamp,
            "warnings": warnings,
            "review_status": "pending_import_approval",
            "input_boundary": BOUNDARY,
            "sensitive_material_excluded": True,
            "excluded_sensitive_material": excluded,
            "summary_payload_sha256": safe_sha256,
        }
        doc = Entity(
            type=EntityType.DOCUMENT,
            value=f"{PROVIDER_NAME} {self.query_type} summary for {subject}",
            properties=common_props | {"document_type": self.document_type},
            source=self.name,
        )
        entities = [doc]
        edges = [Edge(source_id=entity.id, target_id=doc.id, label="provider_summary", source_transform=self.name)]

        for dataset_id in dataset_ids:
            identifier = Entity(
                type=EntityType.IDENTIFIER,
                value=f"breachvip_dataset:{dataset_id}",
                properties=common_props | {"identifier_type": "provider_dataset_id"},
                source=self.name,
            )
            entities.append(identifier)
            edges.append(
                Edge(
                    source_id=doc.id,
                    target_id=identifier.id,
                    label="summarizes_dataset",
                    source_transform=self.name,
                )
            )

        suffix = "identifier" if len(dataset_ids) == 1 else "identifiers"
        return TransformResult(
            entities=entities,
            edges=edges,
            messages=[f"Breach.vip fixture produced 1 summary and {len(dataset_ids)} dataset {suffix}."],
        )


class EmailToBreachVipSummary(_BreachVipSummaryTransform):
    name = "email_to_breachvip_summary"
    display_name = "Email to Breach.vip Summary"
    description = "Imports a reviewed summary-only Breach.vip email exposure result from pasted JSON"
    input_types = [EntityType.EMAIL_ADDRESS]
    document_type = "provider_exposure_summary"
    query_type = "email"


class UsernameToBreachVipSummary(_BreachVipSummaryTransform):
    name = "username_to_breachvip_summary"
    display_name = "Username to Breach.vip Summary"
    description = "Imports a reviewed summary-only Breach.vip username alias result from pasted JSON"
    input_types = [EntityType.USERNAME]
    document_type = "provider_alias_summary"
    query_type = "username"


class PhoneToBreachVipSummary(_BreachVipSummaryTransform):
    name = "phone_to_breachvip_summary"
    display_name = "Phone to Breach.vip Summary"
    description = "Imports a reviewed summary-only Breach.vip phone exposure result from pasted JSON"
    input_types = [EntityType.PHONE_NUMBER]
    document_type = "provider_exposure_summary"
    query_type = "phone"
