from datetime import datetime, timezone
from uuid import UUID

from ogi.models import (
    Entity,
    TransformResult,
    TransformRun,
    TransformInfo,
    TransformStatus,
)
from ogi.transforms.base import BaseTransform, TransformConfig


class TransformEngine:
    def __init__(self) -> None:
        self._transforms: dict[str, BaseTransform] = {}
        self._runs: dict[UUID, TransformRun] = {}

    def register(self, transform: BaseTransform) -> None:
        self._transforms[transform.name] = transform

    def get_transform(self, name: str) -> BaseTransform | None:
        return self._transforms.get(name)

    def list_transforms(self) -> list[TransformInfo]:
        return [
            TransformInfo(
                name=t.name,
                display_name=t.display_name,
                description=t.description,
                input_types=t.input_types,
                output_types=t.output_types,
                category=t.category,
                settings=[s.model_dump(mode="json") for s in getattr(t, "settings", [])],
            )
            for t in self._transforms.values()
        ]

    def list_for_entity(self, entity: Entity) -> list[TransformInfo]:
        return [
            TransformInfo(
                name=t.name,
                display_name=t.display_name,
                description=t.description,
                input_types=t.input_types,
                output_types=t.output_types,
                category=t.category,
                settings=[s.model_dump(mode="json") for s in getattr(t, "settings", [])],
            )
            for t in self._transforms.values()
            if t.can_run_on(entity)
        ]

    async def run_transform(
        self,
        name: str,
        entity: Entity,
        project_id: UUID,
        config: TransformConfig | None = None,
    ) -> TransformRun:
        transform = self._transforms.get(name)
        if transform is None:
            raise ValueError(f"Transform '{name}' not found")

        if not transform.can_run_on(entity):
            raise ValueError(
                f"Transform '{name}' cannot run on entity type '{entity.type.value}'"
            )

        run = TransformRun(
            project_id=project_id,
            transform_name=name,
            input_entity_id=entity.id,
            status=TransformStatus.RUNNING,
        )
        self._runs[run.id] = run

        try:
            result = await transform.run(entity, config or TransformConfig())
            run.status = TransformStatus.COMPLETED
            run.result = result.model_dump(mode="json")
        except Exception as e:
            run.status = TransformStatus.FAILED
            run.error = str(e)
            run.result = TransformResult(messages=[f"Error: {e}"]).model_dump(mode="json")

        run.completed_at = datetime.now(timezone.utc)
        self._runs[run.id] = run
        return run

    def get_run(self, run_id: UUID) -> TransformRun | None:
        return self._runs.get(run_id)

    def load_plugins(self, plugin_dirs: list[str]) -> "PluginEngine":
        """Discover and load plugin transforms from the given directories."""
        from ogi.engine.plugin_engine import PluginEngine
        engine = PluginEngine(plugin_dirs)
        engine.load_all(self)
        return engine

    def auto_discover(self) -> None:
        """Register all built-in transforms."""
        from ogi.transforms.dns.domain_to_ip import DomainToIP
        from ogi.transforms.dns.domain_to_mx import DomainToMX
        from ogi.transforms.dns.domain_to_ns import DomainToNS
        from ogi.transforms.dns.ip_to_domain import IPToDomain
        from ogi.transforms.dns.whois_lookup import WhoisLookup
        from ogi.transforms.ip.ip_to_geolocation import IPToGeolocation
        from ogi.transforms.ip.ip_to_asn import IPToASN
        from ogi.transforms.web.url_to_headers import URLToHeaders
        from ogi.transforms.web.domain_to_urls import DomainToURLs
        from ogi.transforms.email.email_to_domain import EmailToDomain
        from ogi.transforms.email.domain_to_emails import DomainToEmails
        from ogi.transforms.cert.domain_to_certs import DomainToCerts
        from ogi.transforms.cert.cert_transparency import CertTransparency
        from ogi.transforms.social.username_search import UsernameSearch
        from ogi.transforms.hash.hash_lookup import HashLookup
        from ogi.transforms.org.organization_to_team_members import OrganizationToTeamMembers

        for cls in [
            DomainToIP, DomainToMX, DomainToNS, IPToDomain, WhoisLookup,
            IPToGeolocation, IPToASN,
            URLToHeaders, DomainToURLs,
            EmailToDomain, DomainToEmails,
            DomainToCerts, CertTransparency,
            UsernameSearch, HashLookup,
            OrganizationToTeamMembers,
        ]:
            self.register(cls())
