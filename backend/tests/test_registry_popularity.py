from __future__ import annotations

import pytest

from ogi.cli.registry import RegistryClient


@pytest.mark.asyncio
async def test_apply_dynamic_popularity_overrides_thumbs_and_recomputes_score(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = RegistryClient(cache_dir=tmp_path)
    index = {
        "transforms": [
            {
                "slug": "domain-to-ip",
                "popularity": {
                    "thumbs_up": 0,
                    "thumbs_down": 0,
                    "total_contributors": 3,
                    "commits_last_90_days": 7,
                    "discussion_url": "",
                    "computed_score": 16,
                },
            }
        ]
    }

    async def fake_dynamic(slugs: set[str], force: bool = False):  # type: ignore[no-untyped-def]
        assert slugs == {"domain-to-ip"}
        assert force is False
        return {
            "domain-to-ip": {
                "thumbs_up": 5,
                "thumbs_down": 1,
                "discussion_url": "https://github.com/opengraphintel/ogi-transforms/discussions/17",
            }
        }

    monkeypatch.setattr(client, "get_dynamic_popularity", fake_dynamic)

    merged = await client.apply_dynamic_popularity(index)
    pop = merged["transforms"][0]["popularity"]
    assert pop["thumbs_up"] == 5
    assert pop["thumbs_down"] == 1
    assert pop["discussion_url"].endswith("/17")
    assert pop["computed_score"] == ((5 * 2) + (3 * 3) + 7 - 1)


def test_extract_discussion_slug_from_body() -> None:
    slug = RegistryClient._extract_discussion_slug(
        "## Name\n\n**Slug:** `domain-to-ip`\n",
        {"domain-to-ip", "other"},
    )
    assert slug == "domain-to-ip"


def test_search_in_index_filters_by_query_and_category(tmp_path) -> None:
    client = RegistryClient(cache_dir=tmp_path)
    index = {
        "transforms": [
            {"slug": "domain-to-ip", "display_name": "Domain to IP", "category": "dns"},
            {"slug": "email-breach", "display_name": "Email Breach", "category": "email"},
        ]
    }

    results = client.search_in_index(index, "domain", category="dns")
    assert [t["slug"] for t in results] == ["domain-to-ip"]
