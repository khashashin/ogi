import json

import pytest

from ogi.engine.transform_engine import TransformEngine
from ogi.models import Entity, EntityType
from ogi.transforms.base import TransformConfig
from ogi.transforms.breachvip import (
    EmailToBreachVipSummary,
    PhoneToBreachVipSummary,
    UsernameToBreachVipSummary,
)


def breachvip_payload():
    return {
        "result_status": "exposed",
        "summary_counts": {
            "breach_count": 3,
            "alias_hit_count": 2,
            "paste_count": 1,
            "stealer_log_count": 0,
        },
        "dataset_ids": ["synthetic-combo-1", "synthetic-public-forum-2"],
        "warnings": ["summary-only fixture; no raw records imported"],
        "raw_records": [
            {
                "email": "fixture.person@example.invalid",
                "password": "never-import-password",
                "password_hash": "never-import-hash",
                "raw_secret": "never-import-secret",
            }
        ],
    }


@pytest.mark.asyncio
async def test_email_to_breachvip_summary_imports_summary_only_document_and_dataset_ids():
    entity = Entity(type=EntityType.EMAIL_ADDRESS, value="fixture.person@example.invalid")
    result = await EmailToBreachVipSummary().run(
        entity,
        TransformConfig(
            settings={
                "result_json": json.dumps(breachvip_payload()),
                "source_timestamp": "2026-05-25T22:30:00Z",
            }
        ),
    )

    docs = [row for row in result.entities if row.type == EntityType.DOCUMENT]
    identifiers = [row for row in result.entities if row.type == EntityType.IDENTIFIER]
    serialized = json.dumps([row.model_dump(mode="json") for row in result.entities], sort_keys=True)

    assert len(docs) == 1
    assert docs[0].properties["document_type"] == "provider_exposure_summary"
    assert docs[0].properties["summary_only"] is True
    assert docs[0].properties["summary_counts"]["breach_count"] == 3
    assert docs[0].properties["excluded_sensitive_material"] == ["raw_records"]
    assert [row.value for row in identifiers] == [
        "breachvip_dataset:synthetic-combo-1",
        "breachvip_dataset:synthetic-public-forum-2",
    ]
    assert "never-import-password" not in serialized
    assert "password_hash" not in serialized
    assert result.messages == ["Breach.vip fixture produced 1 summary and 2 dataset identifiers."]


@pytest.mark.asyncio
async def test_username_to_breachvip_summary_imports_alias_summary_without_raw_rows():
    entity = Entity(type=EntityType.USERNAME, value="fixture-osint-handle")
    result = await UsernameToBreachVipSummary().run(
        entity,
        TransformConfig(settings={"result_json": json.dumps(breachvip_payload())}),
    )

    docs = [row for row in result.entities if row.type == EntityType.DOCUMENT]
    serialized = json.dumps([row.model_dump(mode="json") for row in result.entities], sort_keys=True)

    assert len(docs) == 1
    assert docs[0].properties["document_type"] == "provider_alias_summary"
    assert docs[0].properties["summary_counts"]["alias_hit_count"] == 2
    assert "raw_secret" not in serialized
    assert "never-import" not in serialized


@pytest.mark.asyncio
async def test_phone_to_breachvip_summary_keeps_negative_reviewed_summary():
    entity = Entity(type=EntityType.PHONE_NUMBER, value="+15555550100")
    payload = breachvip_payload() | {
        "result_status": "not_found",
        "summary_counts": {"breach_count": 0, "alias_hit_count": 0, "paste_count": 0, "stealer_log_count": 0},
        "dataset_ids": [],
    }

    result = await PhoneToBreachVipSummary().run(
        entity,
        TransformConfig(settings={"result_json": json.dumps(payload)}),
    )

    docs = [row for row in result.entities if row.type == EntityType.DOCUMENT]
    identifiers = [row for row in result.entities if row.type == EntityType.IDENTIFIER]

    assert len(docs) == 1
    assert docs[0].properties["result_status"] == "not_found"
    assert docs[0].properties["summary_counts"]["breach_count"] == 0
    assert identifiers == []


def test_transform_engine_discovers_breachvip_summary_transforms():
    engine = TransformEngine()
    engine.auto_discover()
    names = {row.name for row in engine.list_transforms()}

    assert {
        "email_to_breachvip_summary",
        "username_to_breachvip_summary",
        "phone_to_breachvip_summary",
    } <= names
