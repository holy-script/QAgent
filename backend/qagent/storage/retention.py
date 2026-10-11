"""
Per-app retention: finished runs older than the app's `retention_days` are deleted (rows and stored files),
except the newest `retention_keep_last` runs, which are always kept. An app with no `retention_days` keeps everything.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, List, Set

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.domain import models as m
from qagent.engine.tracing import logger
from qagent.storage.objects import object_store
from qagent.storage.purge import purge_runs, refresh_issues

DONE = ("passed", "failed", "stopped", "error")
INTERVAL_S = 3600


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def expired_runs(session: AsyncSession, app: m.App, busy: Iterable[str] = (),
                       now: datetime | None = None) -> List[m.Run]:
    """Runs this app's policy says can go. Runs still in progress (or in `busy`) are never touched."""
    if not app.retention_days:
        return []
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=app.retention_days)
    runs = (await session.execute(select(m.Run).where(m.Run.app_id == app.id))).scalars().all()
    runs.sort(key=lambda r: _aware(r.started_at or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    protected: Set[str] = {r.id for r in runs[: max(0, app.retention_keep_last)]} | set(busy)
    return [r for r in runs if r.id not in protected and r.status in DONE
            and _aware(r.started_at or datetime.min.replace(tzinfo=timezone.utc)) < cutoff]


async def apply_retention(session: AsyncSession, app: m.App, busy: Iterable[str] = ()) -> dict:
    victims = await expired_runs(session, app, busy)
    if not victims:
        return {"runs_deleted": 0, "files_removed": 0}
    ids = [r.id for r in victims]
    await purge_runs(session, ids)
    await refresh_issues(session, app.id)
    await session.commit()
    files = 0
    for run_id in ids:
        files += await asyncio.to_thread(object_store.delete_prefix, f"apps/{app.id}/runs/{run_id}/")
    return {"runs_deleted": len(ids), "files_removed": files}


async def retention_loop(session_factory: Callable[[], AsyncSession], busy: Callable[[], Set[str]],
                         interval_s: int = INTERVAL_S) -> None:
    """Applies every app's policy once an hour for as long as the server runs."""
    while True:
        try:
            async with session_factory() as session:
                for app in (await session.execute(select(m.App).where(m.App.retention_days.is_not(None)))).scalars().all():
                    result = await apply_retention(session, app, busy())
                    if result["runs_deleted"]:
                        logger.info("retention.applied", app=app.slug, **result)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("retention.failed", error=type(exc).__name__)
        await asyncio.sleep(interval_s)
