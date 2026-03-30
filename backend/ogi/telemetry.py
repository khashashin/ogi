from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

import httpx
from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.cli.installer import get_runtime_ogi_version
from ogi.agent.models import AgentRun
from ogi.config import settings
from ogi.models import (
    Edge,
    Entity,
    PluginInfo,
    Project,
    TelemetryDailyMetric,
    TelemetryIngestPayload,
    TelemetryInstallation,
    TelemetryInstalledTransform,
    TelemetryInstanceSummary,
    TelemetryLocalState,
    TelemetryMetricsSnapshot,
    TelemetryOverviewResponse,
    TelemetryTransformSnapshot,
    TransformRun,
    UserProfile,
)

logger = logging.getLogger("ogi.telemetry")

TELEMETRY_INGEST_URL = "https://ogi.khas.app/api/v1/telemetry/ingest"
TELEMETRY_DOCS_PATH = "/privacy#telemetry"
TELEMETRY_POLL_INTERVAL = 3600


def telemetry_docs_url() -> str:
    if settings.deployment_mode == "cloud":
        return f"https://ogi.khas.app{TELEMETRY_DOCS_PATH}"
    return TELEMETRY_DOCS_PATH


class TelemetryManager:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None

    async def ensure_local_state(self, session: AsyncSession) -> TelemetryLocalState:
        state = await session.get(TelemetryLocalState, 1)
        if state:
            return state
        state = TelemetryLocalState(id=1, instance_id=uuid4())
        session.add(state)
        await session.commit()
        await session.refresh(state)
        return state

    async def build_payload(
        self,
        session: AsyncSession,
        metric_date: date,
        telemetry_level: str,
    ) -> TelemetryIngestPayload:
        state = await self.ensure_local_state(session)
        payload = TelemetryIngestPayload(
            instance_id=state.instance_id,
            instance_created_at=state.instance_created_at if telemetry_level == "full" else None,
            ogi_version=get_runtime_ogi_version(),
            metric_date=metric_date,
            sent_at=datetime.now(timezone.utc),
            telemetry_level=telemetry_level,
            deployment_mode="cloud" if settings.deployment_mode == "cloud" else "self-hosted",
        )
        if telemetry_level == "full":
            payload.metrics = TelemetryMetricsSnapshot(
                projects_total=await self._count(session, Project),
                entities_total=await self._count(session, Entity),
                edges_total=await self._count(session, Edge),
                transform_runs_total=await self._count(session, TransformRun),
                investigator_runs_total=await self._count(session, AgentRun),
                active_users_total=await self._active_users_count(session, metric_date),
            )
            payload.installed_transforms = await self._installed_transforms(session)
        return payload

    async def run_due_cycle(self, session: AsyncSession) -> None:
        if not settings.effective_telemetry_enabled:
            return
        state = await self.ensure_local_state(session)
        telemetry_level = settings.normalized_telemetry_level
        today = datetime.now(timezone.utc).date()
        if telemetry_level == "basic" and state.last_basic_sent_on == today:
            return
        if telemetry_level == "full" and state.last_full_sent_on == today:
            return
        payload = await self.build_payload(session, today, telemetry_level)
        if settings.deployment_mode == "cloud":
            await self.store_ingest_payload(session, payload, country_code="ZZ")
        else:
            await self._post_payload(payload)
        if telemetry_level == "basic":
            state.last_basic_sent_on = today
        else:
            state.last_basic_sent_on = today
            state.last_full_sent_on = today
        state.updated_at = datetime.now(timezone.utc)
        session.add(state)
        await session.commit()

    async def store_ingest_payload(
        self,
        session: AsyncSession,
        payload: TelemetryIngestPayload,
        *,
        country_code: str | None,
    ) -> TelemetryDailyMetric:
        now = datetime.now(timezone.utc)
        installation = await session.get(TelemetryInstallation, payload.instance_id)
        if installation is None:
            installation = TelemetryInstallation(
                instance_id=payload.instance_id,
                first_seen_at=now,
            )
        installation.last_seen_at = now
        installation.instance_created_at = payload.instance_created_at or installation.instance_created_at
        installation.latest_ogi_version = payload.ogi_version
        installation.latest_telemetry_level = payload.telemetry_level
        installation.deployment_mode = payload.deployment_mode
        installation.latest_country_code = country_code or installation.latest_country_code
        session.add(installation)
        await session.flush()

        stmt = select(TelemetryDailyMetric).where(
            TelemetryDailyMetric.instance_id == payload.instance_id,
            TelemetryDailyMetric.metric_date == payload.metric_date,
        )
        existing = (await session.execute(stmt)).scalars().first()
        metric = existing or TelemetryDailyMetric(
            instance_id=payload.instance_id,
            metric_date=payload.metric_date,
        )
        metric.ogi_version = payload.ogi_version
        metric.telemetry_level = payload.telemetry_level
        metric.deployment_mode = payload.deployment_mode
        metric.country_code = country_code
        if payload.metrics is not None:
            metric.projects_total = payload.metrics.projects_total
            metric.entities_total = payload.metrics.entities_total
            metric.edges_total = payload.metrics.edges_total
            metric.transform_runs_total = payload.metrics.transform_runs_total
            metric.investigator_runs_total = payload.metrics.investigator_runs_total
            metric.active_users_total = payload.metrics.active_users_total
        else:
            metric.projects_total = None
            metric.entities_total = None
            metric.edges_total = None
            metric.transform_runs_total = None
            metric.investigator_runs_total = None
            metric.active_users_total = None
        session.add(metric)
        await session.flush()

        await session.execute(
            delete(TelemetryInstalledTransform).where(
                TelemetryInstalledTransform.daily_metric_id == metric.id
            )
        )
        if payload.telemetry_level == "full":
            for item in payload.installed_transforms:
                session.add(
                    TelemetryInstalledTransform(
                        daily_metric_id=metric.id,
                        transform_name=item.name[:255],
                        transform_version=item.version[:64],
                    )
                )
        await session.commit()
        await session.refresh(metric)
        return metric

    async def admin_overview(self, session: AsyncSession) -> TelemetryOverviewResponse:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        active_instances_30d = await self._count_installations_since(session, cutoff)
        self_hosted_instances_30d = await self._count_installations_since(session, cutoff, "self-hosted")
        cloud_instances_30d = await self._count_installations_since(session, cutoff, "cloud")
        latest_metric_date = (await session.execute(select(func.max(TelemetryDailyMetric.metric_date)))).scalar()
        versions_stmt = (
            select(TelemetryInstallation.latest_ogi_version, func.count())
            .group_by(TelemetryInstallation.latest_ogi_version)
            .order_by(func.count().desc(), TelemetryInstallation.latest_ogi_version.desc())
        )
        versions = [
            {"version": version, "count": count}
            for version, count in (await session.execute(versions_stmt)).all()
        ]
        return TelemetryOverviewResponse(
            active_instances_30d=active_instances_30d,
            self_hosted_instances_30d=self_hosted_instances_30d,
            cloud_instances_30d=cloud_instances_30d,
            latest_metric_date=latest_metric_date,
            recent_versions=versions,
        )

    async def list_instances(self, session: AsyncSession, limit: int = 50) -> list[TelemetryInstanceSummary]:
        stmt = (
            select(TelemetryInstallation)
            .order_by(TelemetryInstallation.last_seen_at.desc())
            .limit(limit)
        )
        installations = list((await session.execute(stmt)).scalars().all())
        result: list[TelemetryInstanceSummary] = []
        for installation in installations:
            transforms_stmt = (
                select(TelemetryInstalledTransform.transform_name, TelemetryInstalledTransform.transform_version)
                .join(TelemetryDailyMetric, TelemetryDailyMetric.id == TelemetryInstalledTransform.daily_metric_id)
                .where(TelemetryDailyMetric.instance_id == installation.instance_id)
                .order_by(TelemetryDailyMetric.metric_date.desc(), TelemetryInstalledTransform.transform_name.asc())
            )
            rows = (await session.execute(transforms_stmt)).all()
            seen: set[str] = set()
            transforms: list[TelemetryTransformSnapshot] = []
            for name, version in rows:
                if name in seen:
                    continue
                seen.add(name)
                transforms.append(TelemetryTransformSnapshot(name=name, version=version))
            result.append(
                TelemetryInstanceSummary(
                    instance_id=installation.instance_id,
                    first_seen_at=installation.first_seen_at,
                    last_seen_at=installation.last_seen_at,
                    instance_created_at=installation.instance_created_at,
                    latest_ogi_version=installation.latest_ogi_version,
                    latest_telemetry_level=installation.latest_telemetry_level,
                    deployment_mode=installation.deployment_mode,
                    latest_country_code=installation.latest_country_code,
                    installed_transforms=transforms,
                )
            )
        return result

    async def telemetry_loop(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        while True:
            try:
                async with session_factory() as session:
                    await self.run_due_cycle(session)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telemetry cycle failed")
            await asyncio.sleep(TELEMETRY_POLL_INTERVAL)

    async def _count(self, session: AsyncSession, model) -> int:  # type: ignore[no-untyped-def]
        stmt = select(func.count()).select_from(model)
        return int((await session.execute(stmt)).scalar_one())

    async def _active_users_count(self, session: AsyncSession, metric_date: date) -> int:
        start = datetime.combine(metric_date, time.min, tzinfo=timezone.utc)
        stmt = select(func.count()).select_from(UserProfile).where(UserProfile.last_active_at >= start)
        return int((await session.execute(stmt)).scalar_one())

    async def _installed_transforms(self, session: AsyncSession) -> list[TelemetryTransformSnapshot]:
        stmt = select(PluginInfo.name, PluginInfo.version).order_by(PluginInfo.name.asc())
        return [
            TelemetryTransformSnapshot(name=name, version=version)
            for name, version in (await session.execute(stmt)).all()
        ]

    async def _post_payload(self, payload: TelemetryIngestPayload) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                TELEMETRY_INGEST_URL,
                json=payload.model_dump(mode="json"),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

    async def _count_installations_since(
        self,
        session: AsyncSession,
        cutoff: datetime,
        deployment_mode: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(TelemetryInstallation).where(
            TelemetryInstallation.last_seen_at >= cutoff
        )
        if deployment_mode is not None:
            stmt = stmt.where(TelemetryInstallation.deployment_mode == deployment_mode)
        return int((await session.execute(stmt)).scalar_one())


telemetry_manager = TelemetryManager()
