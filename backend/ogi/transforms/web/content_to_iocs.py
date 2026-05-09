from __future__ import annotations

import importlib
import re
from typing import Callable

from ogi.models import Edge, Entity, EntityType, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig

IP_PATTERN = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
)
EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
URL_PATTERN = re.compile(r"\bhttps?://[^\s<>'\"()]+", re.IGNORECASE)
HASH_PATTERN = re.compile(r"\b(?:[a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64})\b")
DOMAIN_PATTERN = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")


class ContentToIOCs(BaseTransform):
    name = "content_to_iocs"
    display_name = "Content to IOCs"
    description = "Extracts common indicators of compromise from Document content"
    input_types = [EntityType.DOCUMENT]
    output_types = [
        EntityType.URL,
        EntityType.IP_ADDRESS,
        EntityType.DOMAIN,
        EntityType.EMAIL_ADDRESS,
        EntityType.HASH,
    ]
    category = "Web"

    async def run(self, entity: Entity, _config: TransformConfig) -> TransformResult:
        text = str(entity.properties.get("content") or entity.value or "").strip()
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        if not text:
            return TransformResult(messages=["No text content found in document"])

        seen: set[tuple[EntityType, str]] = set()
        total = 0

        def add_ioc(value: str, entity_type: EntityType, label: str) -> None:
            nonlocal total
            normalized = value.strip()
            if not normalized:
                return
            key = (entity_type, normalized.lower())
            if key in seen:
                return
            seen.add(key)

            out = Entity(
                type=entity_type,
                value=normalized,
                properties={"extracted_from": "document_content"},
                source=self.name,
            )
            entities.append(out)
            edges.append(
                Edge(
                    source_id=entity.id,
                    target_id=out.id,
                    label=label,
                    source_transform=self.name,
                )
            )
            total += 1

        used_iocsearcher = self._extract_with_iocsearcher(text, add_ioc)
        if used_iocsearcher:
            messages.append("IOC extraction backend: iocsearcher")
        else:
            self._extract_with_regex(text, add_ioc)
            messages.append("IOC extraction backend: regex fallback")

        if total == 0:
            messages.append("No IOCs found")
        else:
            messages.append(f"Extracted {total} IOC(s)")

        return TransformResult(entities=entities, edges=edges, messages=messages)

    @staticmethod
    def _extract_with_regex(
        text: str,
        add_ioc: Callable[[str, EntityType, str], None],
    ) -> None:
        for value in URL_PATTERN.findall(text):
            add_ioc(value.rstrip(".,;:!?)]}"), EntityType.URL, "mentions")

        for value in EMAIL_PATTERN.findall(text):
            add_ioc(value, EntityType.EMAIL_ADDRESS, "mentions")

        for value in IP_PATTERN.findall(text):
            add_ioc(value, EntityType.IP_ADDRESS, "resolves to")

        for value in HASH_PATTERN.findall(text):
            add_ioc(value.lower(), EntityType.HASH, "contains hash")

        for value in DOMAIN_PATTERN.findall(text):
            domain = value.lower().rstrip(".")
            if "@" in domain:
                continue
            if domain.startswith(("http://", "https://")):
                continue
            add_ioc(domain, EntityType.DOMAIN, "mentions")

    @staticmethod
    def _extract_with_iocsearcher(
        text: str,
        add_ioc: Callable[[str, EntityType, str], None],
    ) -> bool:
        try:
            searcher_mod = importlib.import_module("iocsearcher.searcher")
            Searcher = getattr(searcher_mod, "Searcher")
            searcher = Searcher()
            items = searcher.search_data(text)
        except Exception:
            return False

        type_map = {
            "url": (EntityType.URL, "mentions"),
            "fqdn": (EntityType.DOMAIN, "mentions"),
            "domain": (EntityType.DOMAIN, "mentions"),
            "email": (EntityType.EMAIL_ADDRESS, "mentions"),
            "email_address": (EntityType.EMAIL_ADDRESS, "mentions"),
            "ip4": (EntityType.IP_ADDRESS, "resolves to"),
            "ipv4": (EntityType.IP_ADDRESS, "resolves to"),
            "ip6": (EntityType.IP_ADDRESS, "resolves to"),
            "ipv6": (EntityType.IP_ADDRESS, "resolves to"),
            "md5": (EntityType.HASH, "contains hash"),
            "sha1": (EntityType.HASH, "contains hash"),
            "sha256": (EntityType.HASH, "contains hash"),
            "hash": (EntityType.HASH, "contains hash"),
        }

        found = False
        for item in items:
            ioc_value = str(getattr(item, "value", "")).strip()
            ioc_type = str(getattr(item, "name", "")).strip().lower()
            if not ioc_value or not ioc_type:
                continue
            mapped = type_map.get(ioc_type)
            if not mapped:
                continue
            entity_type, edge_label = mapped
            if entity_type == EntityType.HASH:
                ioc_value = ioc_value.lower()
            add_ioc(ioc_value, entity_type, edge_label)
            found = True

        return found
