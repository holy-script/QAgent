"""Deleting runs and apps, restart recovery, upload retries, and the artifact.uploaded event."""
import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from conftest import FakeJudge
from qagent.api import main as api_main
from qagent.api.seed import DEMO_APP_ID, seed_demo
from qagent.decision.stub import StubDecider
from qagent.domain import models as m
from qagent.reports.pipeline import run_report_pipeline
from qagent.runs.manager import RunManager, get_run_manager, recover_orphaned_runs
from qagent.storage import db
from qagent.storage.objects import object_store
from qagent.storage import upload_queue as uq

ALL_TABLES = [m.Run, m.FlowRun, m.Step, m.StepTiming, m.Decision, m.FindingRecord, m.EvidenceLink, m.CheckResult,
              m.NetworkCallRecord, m.Artifact, m.SpanRecord, m.LogEntryRecord, m.EventRecord, m.Report, m.Issue,
              m.Playbook, m.PlaybookVersion, m.PlaybookItem, m.ItemLink, m.ModelCall]


@pytest_asyncio.fixture
async def api(shop, mem_sessions, uploader, monkeypatch):
    shop_url, set_bugs = shop
    monkeypatch.setattr(db, "async_session_factory", mem_sessions)
    async with mem_sessions() as s:
        await seed_demo(s)
        app = await s.get(m.App, DEMO_APP_ID)
        app.base_url = shop_url
        await s.commit()
    manager = RunManager(session_factory=mem_sessions, decider_factory=lambda mode: StubDecider(),
                         escalator_factory=lambda mode: None, judge_factory=lambda mode: FakeJudge(),
                         uploader=uploader, report_hook=run_report_pipeline)
    api_main.app.dependency_overrides[get_run_manager] = lambda: manager
    async with AsyncClient(transport=ASGITransport(app=api_main.app), base_url="http://test") as c:
        c.manager, c.sessions = manager, mem_sessions
        yield c
    api_main.app.dependency_overrides.clear()


async def run_and_wait(api, **body):
    run_id = (await api.post(f"/apps/{DEMO_APP_ID}/runs", json={"mode": "stub", "include_edge_cases": False, **body})).json()["id"]
    for _ in range(480):
        if run_id not in api.manager.active:
            return run_id
        await asyncio.sleep(0.25)
    raise AssertionError("run did not finish")


async def count(sessions, model):
    async with sessions() as s:
        return len((await s.execute(select(model))).scalars().all())


@pytest.mark.asyncio
async def test_deleting_a_run_removes_its_data_files_and_recounts_bugs(api):
    run1 = await run_and_wait(api, flow_keys=["add-to-cart"])
    run2 = await run_and_wait(api, flow_keys=["add-to-cart"])
    issues = (await api.get(f"/apps/{DEMO_APP_ID}/issues")).json()
    assert issues and all(i["occurrences"] == 2 for i in issues)

    r = await api.delete(f"/runs/{run2}")
    assert r.status_code == 200 and r.json()["deleted"]["runs"] == 1 and r.json()["files_removed"] > 0
    assert (await api.get(f"/runs/{run2}")).status_code == 404
    after = (await api.get(f"/apps/{DEMO_APP_ID}/issues")).json()
    assert len(after) == len(issues) and all(i["occurrences"] == 1 and i["last_seen_run_id"] == run1 for i in after)
    assert not object_store.delete_prefix(f"apps/{DEMO_APP_ID}/runs/{run2}/")  # nothing left to remove

    await api.delete(f"/runs/{run1}")  # the last proof of each bug is gone, so the bugs go too
    assert (await api.get(f"/apps/{DEMO_APP_ID}/issues")).json() == []
    assert (await api.delete("/runs/nope")).status_code == 404


@pytest.mark.asyncio
async def test_deleting_an_app_removes_every_row_and_file(api):
    await run_and_wait(api, flow_keys=["add-to-cart", "payment"])
    other = (await api.post("/apps", json={"base_url": "http://other.test", "name": "Other"})).json()
    for model in (m.Run, m.FlowRun, m.Step, m.Decision, m.NetworkCallRecord, m.Artifact, m.EventRecord, m.Playbook, m.PlaybookItem):
        assert await count(api.sessions, model) > 0, model.__name__  # there is something to delete
    assert await count(api.sessions, m.Run) == 1

    r = await api.delete(f"/apps/{DEMO_APP_ID}")
    assert r.status_code == 200 and r.json()["deleted"]["apps"] == 1 and r.json()["files_removed"] > 0
    for model in ALL_TABLES:
        assert await count(api.sessions, model) == 0, model.__name__
    assert (await api.get(f"/apps/{DEMO_APP_ID}")).status_code == 404
    assert (await api.get(f"/apps/{other['slug']}")).status_code == 200  # other apps are untouched
    assert not object_store.delete_prefix(f"apps/{DEMO_APP_ID}/")


@pytest.mark.asyncio
async def test_cannot_delete_while_a_run_is_in_progress(api):
    run_id = (await api.post(f"/apps/{DEMO_APP_ID}/runs", json={"mode": "stub"})).json()["id"]
    assert (await api.delete(f"/apps/{DEMO_APP_ID}")).status_code == 409
    assert (await api.delete(f"/runs/{run_id}")).status_code == 409
    await api.post(f"/runs/{run_id}/stop")
    for _ in range(480):
        if run_id not in api.manager.active:
            break
        await asyncio.sleep(0.25)
    assert (await api.delete(f"/apps/{DEMO_APP_ID}")).status_code == 200


@pytest.mark.asyncio
async def test_orphaned_runs_are_closed_on_startup(mem_sessions):
    async with mem_sessions() as s:
        s.add(m.Run(id="r-orphan", app_id="a", status="running"))
        s.add(m.FlowRun(id="f1", run_id="r-orphan", flow_key="x", status="running"))
        s.add(m.EventRecord(run_id="r-orphan", seq=7, type="run.started", payload={}))
        s.add(m.Run(id="r-done", app_id="a", status="passed"))
        await s.commit()
    assert await recover_orphaned_runs(mem_sessions) == 1
    async with mem_sessions() as s:
        run = await s.get(m.Run, "r-orphan")
        assert run.status == "error" and run.finished_at is not None
        assert (await s.get(m.FlowRun, "f1")).status == "failed"
        last = (await s.execute(select(m.EventRecord).where(m.EventRecord.run_id == "r-orphan").order_by(m.EventRecord.seq.desc()))).scalars().first()
        assert (last.seq, last.type) == (8, "error")  # SSE viewers see a terminal event
        assert (await s.get(m.Run, "r-done")).status == "passed"
    assert await recover_orphaned_runs(mem_sessions) == 0


@pytest.mark.asyncio
async def test_uploads_are_retried_and_failures_never_raise(mem_sessions, monkeypatch, tmp_path):
    monkeypatch.setattr(uq, "BACKOFF_S", (0, 0, 0))
    monkeypatch.setattr(uq, "async_session_factory", mem_sessions)
    calls = {"n": 0}

    def flaky(key, body, content_type="x"):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("storage hiccup")

    monkeypatch.setattr(uq.object_store, "put_object", flaky)
    q = uq.UploadQueue()
    q.start()
    done = []

    async def on_done(artifact):
        done.append(artifact.object_key)

    await q.enqueue(key="k/ok", data=b"x", content_type="text/plain", run_id="r", on_done=on_done)
    await q.drain()
    assert calls["n"] == 3 and done == ["k/ok"] and q.failed == []  # succeeded on the third attempt

    def broken(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(uq.object_store, "put_object", broken)
    await q.enqueue(key="k/bad", data=b"x", content_type="text/plain", run_id="r", on_done=on_done)
    await q.drain()
    assert q.failed == ["k/bad"] and done == ["k/ok"]  # recorded, callback skipped, queue still alive
    await q.stop()


@pytest.mark.asyncio
async def test_runs_emit_artifact_uploaded_and_mark_steps_complete(api):
    run_id = await run_and_wait(api, flow_keys=["add-to-cart"])
    async with api.sessions() as s:
        events = (await s.execute(select(m.EventRecord).where(m.EventRecord.run_id == run_id))).scalars().all()
        uploaded = [e for e in events if e.type == "artifact.uploaded"]
        steps = (await s.execute(select(m.Step))).scalars().all()
    assert len(uploaded) >= 9 and {"screenshot_after", "screenshot_before", "trace"} <= {e.payload["kind"] for e in uploaded}
    assert steps and all(st.artifacts_complete for st in steps)
