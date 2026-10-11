"""Per-app retention: only that app's old, finished runs go; the newest N and anything running stay."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from qagent.api.seed import DEMO_APP_ID
from qagent.domain import models as m
from qagent.storage.objects import object_store
from qagent.storage.retention import apply_retention, expired_runs
from test_lifecycle import api  # noqa: F401  (fixture)

NOW = datetime.now(timezone.utc)


async def seed_runs(sessions, app_id, ages, status="passed"):
    ids = []
    async with sessions() as s:
        for age in ages:
            r = m.Run(app_id=app_id, status=status, started_at=NOW - timedelta(days=age))
            s.add(r)
            await s.flush()
            s.add(m.FlowRun(run_id=r.id, flow_key="f"))
            ids.append(r.id)
            object_store.put_object(f"apps/{app_id}/runs/{r.id}/x.txt", b"x", "text/plain")
        await s.commit()
    return ids


@pytest.mark.asyncio
async def test_policy_keeps_newest_and_running_and_other_apps(api):  # noqa: F811
    sessions = api.sessions
    async with sessions() as s:
        other = m.App(slug="other", name="Other", base_url="http://x", retention_days=1, retention_keep_last=0)
        s.add(other)
        await s.commit()
        other_id = other.id
    old = await seed_runs(sessions, DEMO_APP_ID, [40, 35, 30, 2, 1])      # five finished runs
    running = await seed_runs(sessions, DEMO_APP_ID, [60], status="running")
    theirs = await seed_runs(sessions, other_id, [5, 4])
    async with sessions() as s:
        app = await s.get(m.App, DEMO_APP_ID)
        app.retention_days, app.retention_keep_last = 7, 2
        await s.commit()
        victims = {r.id for r in await expired_runs(s, app)}
    # runs older than 7 days, minus the 2 newest overall: the 3 old finished runs; the running one is protected
    assert victims == set(old[:3]) and running[0] not in victims

    async with sessions() as s:
        app = await s.get(m.App, DEMO_APP_ID)
        result = await apply_retention(s, app)
    assert result["runs_deleted"] == 3 and result["files_removed"] >= 3
    async with sessions() as s:
        left = {r.id for r in (await s.execute(select(m.Run))).scalars().all()}
        assert set(old[:3]).isdisjoint(left) and {*old[3:], *running, *theirs} <= left  # the other app is untouched here
        assert not (await s.execute(select(m.FlowRun).where(m.FlowRun.run_id == old[0]))).scalars().all()
    assert object_store.get_bytes(f"apps/{DEMO_APP_ID}/runs/{old[0]}/x.txt") is None
    assert object_store.get_bytes(f"apps/{DEMO_APP_ID}/runs/{old[3]}/x.txt") == b"x"


@pytest.mark.asyncio
async def test_no_policy_keeps_everything_and_api_roundtrip(api):  # noqa: F811
    await seed_runs(api.sessions, DEMO_APP_ID, [400, 300])
    status = (await api.get(f"/apps/{DEMO_APP_ID}/retention")).json()
    assert status["retention_days"] is None and status["would_delete"] == 0
    assert (await api.post(f"/apps/{DEMO_APP_ID}/retention/clean")).json()["runs_deleted"] == 0

    r = await api.patch(f"/apps/{DEMO_APP_ID}", json={"retention_days": 30, "retention_keep_last": 0})
    assert r.json()["retention_days"] == 30
    assert (await api.get(f"/apps/{DEMO_APP_ID}/retention")).json()["would_delete"] == 2
    assert (await api.patch(f"/apps/{DEMO_APP_ID}", json={"retention_days": 0})).status_code == 422
    assert (await api.post(f"/apps/{DEMO_APP_ID}/retention/clean")).json()["runs_deleted"] == 2
    assert (await api.get(f"/apps/{DEMO_APP_ID}/retention")).json()["total_runs"] == 0
