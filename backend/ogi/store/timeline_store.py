from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ogi.models import TimelineBucket, TimelineResponse
from ogi.store.project_event_store import ProjectEventStore


def _floor_dt(value: datetime, interval: str) -> datetime:
    if interval == "minute":
        return value.replace(second=0, microsecond=0)
    if interval == "hour":
        return value.replace(minute=0, second=0, microsecond=0)
    if interval == "week":
        day_start = value.replace(hour=0, minute=0, second=0, microsecond=0)
        return day_start - timedelta(days=day_start.weekday())
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _step(interval: str) -> timedelta:
    if interval == "minute":
        return timedelta(minutes=1)
    if interval == "hour":
        return timedelta(hours=1)
    if interval == "week":
        return timedelta(days=7)
    return timedelta(days=1)


class TimelineStore:
    """Builds bucketed timeline views from project events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.event_store = ProjectEventStore(session)

    async def get_timeline(
        self,
        project_id: UUID,
        interval: str = "day",
        since: datetime | None = None,
        until: datetime | None = None,
        max_events: int = 2000,
    ) -> TimelineResponse:
        events = await self.event_store.list_events(project_id, since=since, until=until, limit=max_events)
        if not events:
            return TimelineResponse(interval=interval, window_start=since, window_end=until, total_events=0, buckets=[])

        starts = [event.occurred_at for event in events]
        window_start = since or min(starts)
        window_end = until or max(starts)
        bucket_start = _floor_dt(window_start, interval)
        bucket_step = _step(interval)

        buckets: dict[datetime, TimelineBucket] = {}
        for event in events:
            key = _floor_dt(event.occurred_at, interval)
            if key not in buckets:
                buckets[key] = TimelineBucket(
                    bucket_start=key,
                    bucket_end=key + bucket_step,
                    count=0,
                    event_types={},
                )
            row = buckets[key]
            row.count += 1
            row.event_types[event.event_type] = row.event_types.get(event.event_type, 0) + 1

        ordered = [buckets[k] for k in sorted(buckets.keys())]
        return TimelineResponse(
            interval=interval,
            window_start=window_start,
            window_end=window_end,
            total_events=len(events),
            buckets=ordered,
        )
