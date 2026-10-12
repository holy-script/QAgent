from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.api.deps import get_session
from qagent.api.mappers import iso
from qagent.domain import models as m
from qagent.domain.schemas import DashboardApp, DashboardBug, DashboardDay, DashboardResponse, DashboardRun

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
FAILED = ("failed", "stopped", "error")


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("", response_model=DashboardResponse)
async def dashboard(days: int = Query(30, ge=1, le=365), session: AsyncSession = Depends(get_session)):
    """Everything the home dashboard shows, across all apps, for the last `days` days."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    apps = (await session.execute(select(m.App).order_by(m.App.created_at))).scalars().all()
    names = {a.id: a for a in apps}
    runs = (await session.execute(select(m.Run))).scalars().all()
    runs.sort(key=lambda r: _aware(r.started_at) if r.started_at else datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    in_period = [r for r in runs if r.started_at and _aware(r.started_at) >= since]
    finished = [r for r in in_period if r.status in ("passed", *FAILED)]

    per_day: Dict[str, DashboardDay] = {}
    for i in range(days):
        d = (since + timedelta(days=i + 1)).date().isoformat()
        per_day[d] = DashboardDay(date=d)
    for r in in_period:
        day = per_day.get(_aware(r.started_at).date().isoformat())
        if day is None:
            continue
        t = r.totals or {}
        if r.status == "passed":
            day.passed += 1
        elif r.status in FAILED:
            day.failed += 1
        day.findings += int(t.get("findings_count", 0) or 0)
        day.cost_usd += float(t.get("total_cost_usd", 0) or 0)

    issues = (await session.execute(select(m.Issue))).scalars().all()
    live_issues = [i for i in issues if i.status in ("open", "regressed")]
    by_sev: Dict[str, int] = defaultdict(int)
    for i in live_issues:
        by_sev[i.severity] += 1
    by_status: Dict[str, int] = defaultdict(int)
    for i in issues:
        by_status[i.status] += 1

    per_app: List[DashboardApp] = []
    for a in apps:
        mine = [r for r in runs if r.app_id == a.id]
        mine_period = [r for r in mine if r in in_period]
        done = [r for r in mine_period if r.status in ("passed", *FAILED)]
        per_app.append(DashboardApp(
            slug=a.slug, name=a.name, runs=len(mine_period),
            pass_rate=(sum(r.status == "passed" for r in done) / len(done)) if done else None,
            open_bugs=sum(1 for i in live_issues if i.app_id == a.id),
            last_status=mine[0].status if mine else None, last_run_at=iso(mine[0].started_at) if mine else None,
            recent_statuses=[r.status for r in mine[:12]]))

    cost = sum(float((r.totals or {}).get("total_cost_usd", 0) or 0) for r in in_period)
    durations = [float((r.totals or {}).get("duration_ms", 0) or 0) for r in finished if (r.totals or {}).get("duration_ms")]
    return DashboardResponse(
        days=days, apps=len(apps), runs=len(in_period), passed=sum(r.status == "passed" for r in in_period),
        failed=sum(r.status in FAILED for r in in_period), running=sum(r.status in ("running", "pending") for r in in_period),
        pass_rate=(sum(r.status == "passed" for r in finished) / len(finished)) if finished else None,
        cost_usd=cost, avg_duration_ms=sum(durations) / len(durations) if durations else 0.0,
        avg_cost_usd=cost / len(in_period) if in_period else 0.0, open_bugs=len(live_issues),
        bugs_by_severity=dict(by_sev), bugs_by_status=dict(by_status), series=list(per_day.values()), per_app=per_app,
        recent_runs=[DashboardRun(
            id=r.id, app_slug=names[r.app_id].slug if r.app_id in names else "", app_name=names[r.app_id].name if r.app_id in names else "",
            status=r.status, mode=r.mode, started_at=iso(r.started_at), findings=int((r.totals or {}).get("findings_count", 0) or 0),
            cost_usd=float((r.totals or {}).get("total_cost_usd", 0) or 0), duration_ms=float((r.totals or {}).get("duration_ms", 0) or 0))
            for r in runs[:8]],
        top_bugs=[DashboardBug(
            id=i.id, app_slug=names[i.app_id].slug if i.app_id in names else "", app_name=names[i.app_id].name if i.app_id in names else "",
            title=i.title, severity=i.severity, status=i.status, occurrences=i.occurrences)
            for i in sorted(live_issues, key=lambda i: (SEVERITY_ORDER.get(i.severity, 9), -i.occurrences))[:6]],
    )
