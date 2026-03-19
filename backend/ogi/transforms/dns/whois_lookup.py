import asyncio
import logging
from collections.abc import Iterable

import httpx
import whois

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig

_WHOIS_LOGGER = logging.getLogger("whois.whois")
_IANA_RDAP_BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"


class WhoisLookup(BaseTransform):
    name = "whois_lookup"
    display_name = "WHOIS Lookup"
    description = "Retrieves WHOIS registration data for a domain"
    input_types = [EntityType.DOMAIN]
    output_types = [EntityType.ORGANIZATION, EntityType.PERSON, EntityType.EMAIL_ADDRESS]
    category = "DNS"

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        domain = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        try:
            w = await self._lookup_whois(domain)
            self._apply_whois_result(entity, domain, w, entities, edges, messages)
        except Exception as e:
            messages.append(f"WHOIS error: {e}")
            try:
                rdap = await self._lookup_rdap(domain)
                self._apply_rdap_result(entity, domain, rdap, entities, edges, messages)
                messages.append("RDAP fallback succeeded.")
            except Exception as rdap_error:
                messages.append(f"RDAP fallback error: {rdap_error}")

        return TransformResult(entities=entities, edges=edges, messages=messages)

    async def _lookup_whois(self, domain: str):
        previous_disabled = _WHOIS_LOGGER.disabled
        try:
            _WHOIS_LOGGER.disabled = True
            return await asyncio.to_thread(whois.whois, domain)
        finally:
            _WHOIS_LOGGER.disabled = previous_disabled

    async def _lookup_rdap(self, domain: str) -> dict:
        tld = domain.rsplit(".", 1)[-1].lower()

        async with httpx.AsyncClient(timeout=10.0) as client:
            bootstrap_response = await client.get(_IANA_RDAP_BOOTSTRAP_URL)
            bootstrap_response.raise_for_status()
            bootstrap = bootstrap_response.json()

            rdap_base = self._resolve_rdap_base(bootstrap, tld)
            if not rdap_base:
                raise RuntimeError(f"No RDAP bootstrap entry found for .{tld}")

            rdap_response = await client.get(f"{rdap_base.rstrip('/')}/domain/{domain}")
            rdap_response.raise_for_status()
            payload = rdap_response.json()

        if not isinstance(payload, dict):
            raise RuntimeError("RDAP returned an unexpected payload")
        return payload

    def _resolve_rdap_base(self, bootstrap: dict, tld: str) -> str | None:
        services = bootstrap.get("services")
        if not isinstance(services, list):
            return None

        for entry in services:
            if not isinstance(entry, list) or len(entry) < 2:
                continue
            suffixes, urls = entry[0], entry[1]
            if not isinstance(suffixes, list) or not isinstance(urls, list):
                continue
            if tld not in {str(item).lower() for item in suffixes}:
                continue
            for candidate in urls:
                value = str(candidate).strip()
                if value:
                    return value
        return None

    def _apply_whois_result(
        self,
        entity: Entity,
        domain: str,
        w,
        entities: list[Entity],
        edges: list[Edge],
        messages: list[str],
    ) -> None:
        if w.registrar:
            registrar_entity = Entity(
                type=EntityType.ORGANIZATION,
                value=str(w.registrar),
                properties={"role": "registrar", "domain": domain},
                source=self.name,
            )
            entities.append(registrar_entity)
            edges.append(Edge(
                source_id=entity.id,
                target_id=registrar_entity.id,
                label="registered via",
                source_transform=self.name,
            ))
            messages.append(f"Registrar: {w.registrar}")

        if w.org:
            org_entity = Entity(
                type=EntityType.ORGANIZATION,
                value=str(w.org),
                properties={"role": "registrant", "domain": domain},
                source=self.name,
            )
            entities.append(org_entity)
            edges.append(Edge(
                source_id=entity.id,
                target_id=org_entity.id,
                label="registered to",
                source_transform=self.name,
            ))
            messages.append(f"Organization: {w.org}")

        if w.name and isinstance(w.name, str):
            person_entity = Entity(
                type=EntityType.PERSON,
                value=w.name,
                properties={"role": "registrant", "domain": domain},
                source=self.name,
            )
            entities.append(person_entity)
            edges.append(Edge(
                source_id=entity.id,
                target_id=person_entity.id,
                label="registrant",
                source_transform=self.name,
            ))
            messages.append(f"Registrant: {w.name}")

        emails = w.emails if isinstance(w.emails, list) else ([w.emails] if w.emails else [])
        for email in emails:
            email_entity = Entity(
                type=EntityType.EMAIL_ADDRESS,
                value=str(email),
                properties={"domain": domain, "source": "whois"},
                source=self.name,
            )
            entities.append(email_entity)
            edges.append(Edge(
                source_id=entity.id,
                target_id=email_entity.id,
                label="whois email",
                source_transform=self.name,
            ))
            messages.append(f"Email: {email}")

        whois_props: dict[str, str] = {}
        if w.creation_date:
            date = w.creation_date[0] if isinstance(w.creation_date, list) else w.creation_date
            whois_props["whois_creation_date"] = str(date)
        if w.expiration_date:
            date = w.expiration_date[0] if isinstance(w.expiration_date, list) else w.expiration_date
            whois_props["whois_expiration_date"] = str(date)
        if w.updated_date:
            date = w.updated_date[0] if isinstance(w.updated_date, list) else w.updated_date
            whois_props["whois_updated_date"] = str(date)
        if w.dnssec:
            whois_props["dnssec"] = str(w.dnssec)
        if w.status:
            statuses = w.status if isinstance(w.status, list) else [w.status]
            whois_props["whois_status"] = ", ".join(str(s) for s in statuses)

        if whois_props:
            enriched = entity.model_copy(update={
                "properties": {**entity.properties, **whois_props},
            })
            entities.append(enriched)
            for key, val in whois_props.items():
                messages.append(f"{key}: {val}")

    def _apply_rdap_result(
        self,
        entity: Entity,
        domain: str,
        rdap: dict,
        entities: list[Entity],
        edges: list[Edge],
        messages: list[str],
    ) -> None:
        rdap_props: dict[str, str] = {}

        registrar = self._find_entity_name_by_role(rdap, {"registrar"})
        if registrar:
            registrar_entity = Entity(
                type=EntityType.ORGANIZATION,
                value=registrar,
                properties={"role": "registrar", "domain": domain, "source": "rdap"},
                source=self.name,
            )
            entities.append(registrar_entity)
            edges.append(Edge(
                source_id=entity.id,
                target_id=registrar_entity.id,
                label="registered via",
                source_transform=self.name,
            ))
            messages.append(f"Registrar (RDAP): {registrar}")

        registrant = self._find_entity_name_by_role(rdap, {"registrant"})
        if registrant:
            registrant_entity = Entity(
                type=EntityType.ORGANIZATION,
                value=registrant,
                properties={"role": "registrant", "domain": domain, "source": "rdap"},
                source=self.name,
            )
            entities.append(registrant_entity)
            edges.append(Edge(
                source_id=entity.id,
                target_id=registrant_entity.id,
                label="registered to",
                source_transform=self.name,
            ))
            messages.append(f"Organization (RDAP): {registrant}")

        for email in self._extract_rdap_emails(rdap):
            email_entity = Entity(
                type=EntityType.EMAIL_ADDRESS,
                value=email,
                properties={"domain": domain, "source": "rdap"},
                source=self.name,
            )
            entities.append(email_entity)
            edges.append(Edge(
                source_id=entity.id,
                target_id=email_entity.id,
                label="rdap email",
                source_transform=self.name,
            ))
            messages.append(f"Email (RDAP): {email}")

        for event in rdap.get("events", []):
            if not isinstance(event, dict):
                continue
            action = str(event.get("eventAction") or "").strip().lower()
            date = str(event.get("eventDate") or "").strip()
            if not date:
                continue
            if action == "registration":
                rdap_props["whois_creation_date"] = date
            elif action == "expiration":
                rdap_props["whois_expiration_date"] = date
            elif action in {"last changed", "last update of rdap database", "last update of whois database"}:
                rdap_props["whois_updated_date"] = date

        statuses = rdap.get("status")
        if isinstance(statuses, list) and statuses:
            rdap_props["whois_status"] = ", ".join(str(item) for item in statuses if str(item).strip())

        secure_dns = rdap.get("secureDNS")
        if isinstance(secure_dns, dict) and "delegationSigned" in secure_dns:
            rdap_props["dnssec"] = str(bool(secure_dns.get("delegationSigned"))).lower()

        if rdap_props:
            enriched = entity.model_copy(update={
                "properties": {**entity.properties, **rdap_props},
            })
            entities.append(enriched)
            for key, val in rdap_props.items():
                messages.append(f"{key}: {val}")

    def _find_entity_name_by_role(self, rdap: dict, target_roles: set[str]) -> str | None:
        for row in rdap.get("entities", []):
            if not isinstance(row, dict):
                continue
            roles = {
                str(role).strip().lower()
                for role in row.get("roles", [])
                if str(role).strip()
            }
            if not roles.intersection(target_roles):
                continue
            name = self._extract_vcard_value(row.get("vcardArray"), "fn")
            if name:
                return name
        return None

    def _extract_rdap_emails(self, rdap: dict) -> list[str]:
        seen: set[str] = set()
        emails: list[str] = []
        for row in rdap.get("entities", []):
            if not isinstance(row, dict):
                continue
            email = self._extract_vcard_value(row.get("vcardArray"), "email")
            if not email:
                continue
            normalized = email.strip().lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            emails.append(email)
        return emails

    def _extract_vcard_value(self, vcard_array: object, field_name: str) -> str | None:
        if not isinstance(vcard_array, list) or len(vcard_array) < 2:
            return None
        properties = vcard_array[1]
        if not isinstance(properties, Iterable):
            return None

        for item in properties:
            if not isinstance(item, list) or len(item) < 4:
                continue
            if str(item[0]).strip().lower() != field_name:
                continue
            value = item[3]
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
