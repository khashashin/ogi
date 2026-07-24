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
    long_description = (
        "Reads the content property of a Document entity, falling back to the entity "
        "value, and pulls indicators out of that text. It first tries the iocsearcher "
        "library and maps its url, fqdn, domain, email, IPv4, IPv6, md5, sha1 and sha256 "
        "findings onto OGI entities; if that library is missing or raises, it falls back "
        "to built-in regular expressions covering URLs, email addresses, IPv4 addresses, "
        "32, 40 and 64 character hex hashes, and dotted domain names. The messages state "
        "which backend ran. Each indicator, deduplicated case-insensitively per type, "
        "becomes a URL, EmailAddress, IPAddress, Hash or Domain entity with "
        "extracted_from set to document_content, linked back to the document by a "
        "'mentions' edge for URLs, domains and emails, a 'resolves to' edge for IP "
        "addresses and a 'contains hash' edge for hashes."
    )
    when_to_use = (
        "Run this on a Document produced by URL to Content, or on any document whose "
        "text you want mined for pivot points, such as a threat report, a paste or a "
        "captured page body. Take the results onward with Domain to IP Address, IP to "
        "ASN, Email to Domain or Hash Lookup."
    )
    limitations = (
        "This is pattern matching over text with no validation, so false positives are "
        "common: version strings and dotted identifiers match the domain pattern, "
        "filenames whose extension resembles a TLD are picked up, and any 32, 40 or 64 "
        "character hex string is treated as a file hash. Defanged indicators such as "
        "hxxp:// or 1.1.1[.]1 are not recognised by the regex fallback. The two backends "
        "do not return identical sets, so results vary with what is installed. Only text "
        "already stored on the document is searched, so anything lost to the content cap "
        "in URL to Content cannot be recovered here."
    )
    example_use_cases = [
        "Mine a captured threat report for domains, IP addresses and file hashes",
        "Pull contact addresses and outbound links out of a scraped page body",
        "Turn a pasted incident writeup into pivotable entities on the graph",
    ]

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
