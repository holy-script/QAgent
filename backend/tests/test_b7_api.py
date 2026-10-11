import asyncio
import json

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from qagent.api import main as api_main
from qagent.api.seed import DEMO_APP_ID, seed_demo
from qagent.domain.models import App
from qagent.runs.manager import RunManager, get_run_manager
from qagent.decision.stub import StubDecider
from qagent.storage import db


def parse_sse(text: str):
    events = []
    for block in text.strip().split("\r\n\r\n"):
        fields = {}
        for line in block.splitlines():
            if ":" in line and not line.startswith(":"):
                k, _, v = line.partition(":")
                fields[k.strip()] = v.strip()
        if "data" in fields:
            events.append({"id": int(fields["id"]), "event": fields["event"], "data": json.loads(fields["data"])})
    return events


@pytest_asyncio.fixture
async def client(shop, mem_sessions, uploader, monkeypatch):
    shop_url, set_bugs = shop
    set_bugs(bug2=False)
    monkeypatch.setattr(db, "async_session_factory", mem_sessions)
    async with mem_sessions() as s:
        await seed_demo(s)
        app = await s.get(App, DEMO_APP_ID)
        app.base_url = shop_url
        await s.commit()

    manager = RunManager(session_factory=mem_sessions, decider_factory=lambda mode: StubDecider(), uploader=uploader)
    api_main.app.dependency_overrides[get_run_manager] = lambda: manager
    async with AsyncClient(transport=ASGITransport(app=api_main.app), base_url="http://test") as ac:
        ac.manager = manager
        yield ac
    api_main.app.dependency_overrides.clear()


async def wait_done(client, run_id, timeout=60):
    for _ in range(timeout * 4):
        run = (await client.get(f"/runs/{run_id}")).json()
        if run["status"] not in ("pending", "running"):
            return run
        await asyncio.sleep(0.25)
    raise AssertionError("run did not finish")


@pytest.mark.asyncio
async def test_run_from_api_streams_persists_and_resumes(client):
    resp = await client.post("/runs", json={"app_id": "demo-shop", "mode": "stub"})
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["id"]

    # Attach while the run is live: replay + follow until RUN_FINISHED.
    sse = await client.get(f"/runs/{run_id}/events")
    events = parse_sse(sse.text)
    seqs = [e["id"] for e in events]
    assert seqs == list(range(1, len(seqs) + 1))
    assert events[0]["event"] == "RUN_STARTED" and events[-1]["event"] == "RUN_FINISHED"
    types = {e["event"] for e in events}
    assert {"FLOW_STARTED", "STEP_OBSERVED", "DECISION_MADE", "NETWORK_CALL", "FINDING_DISCOVERED"} <= types

    run = await wait_done(client, run_id)
    assert run["status"] == "failed"  # demo bugs 1, 3, 4, 5 produce findings
    assert run["totals"]["findings_count"] >= 4

    # Resume from the middle, both via ?after= and the standard Last-Event-ID header.
    mid = seqs[len(seqs) // 2]
    via_query = parse_sse((await client.get(f"/runs/{run_id}/events", params={"after": mid})).text)
    via_header = parse_sse((await client.get(f"/runs/{run_id}/events", headers={"Last-Event-ID": str(mid)})).text)
    assert [e["id"] for e in via_query] == [e["id"] for e in via_header] == [s for s in seqs if s > mid]

    # Read models
    flows = (await client.get(f"/runs/{run_id}/flows")).json()
    assert {f["flow_key"] for f in flows} == {"add-to-cart", "apply-coupon", "payment"}
    assert all(st["timings"]["total_ms"] > 0 for f in flows for st in f["steps"])
    assert any(st["decision"] for f in flows for st in f["steps"])

    findings = (await client.get(f"/runs/{run_id}/findings")).json()
    assert {f["kind"] for f in findings} == {"dom", "network", "formula", "timing"}

    net = (await client.get(f"/runs/{run_id}/network", params={"only_api": True})).json()
    assert net and all(c["is_api"] for c in net)
    assert any(c["status"] == 500 for c in net)

    spans = (await client.get(f"/runs/{run_id}/spans")).json()
    assert any(sp["kind"] == "flow" for sp in spans) and any(sp["parent_span_id"] for sp in spans)

    logs = (await client.get(f"/runs/{run_id}/logs")).json()
    assert isinstance(logs, list)

    assert (await client.get("/runs/nope/events")).status_code == 404


@pytest.mark.asyncio
async def test_stop_run_and_error_paths(client):
    assert (await client.post("/runs", json={"app_id": "missing", "mode": "stub"})).status_code == 404

    run_id = (await client.post("/runs", json={"app_id": "demo-shop", "mode": "stub"})).json()["id"]
    assert (await client.post(f"/runs/{run_id}/stop")).status_code == 200
    run = await wait_done(client, run_id)
    assert run["status"] == "stopped"


@pytest.mark.asyncio
async def test_playbook_upload_versions_and_artifacts(client, uploader, monkeypatch, tmp_path):
    md = "# Playbook: Tiny\nbase_url: http://localhost:8001\n\n## Flow: browse\n### Steps\n1. Open /products\n"
    created = await client.post("/playbooks", json={"app_id": DEMO_APP_ID, "raw_markdown": md})
    assert created.status_code == 201 and created.json()["flows"][0]["key"] == "browse"
    pb_id = created.json()["id"]

    again = await client.post("/playbooks", json={"app_id": DEMO_APP_ID, "raw_markdown": md})
    assert again.json()["current_version_id"] == created.json()["current_version_id"]  # same hash: no new version
    await client.post("/playbooks", json={"app_id": DEMO_APP_ID, "raw_markdown": md + "2. Open /cart\n"})
    versions = (await client.get(f"/playbooks/{pb_id}/versions")).json()
    assert [v["version_no"] for v in versions] == [2, 1]

    assert (await client.post("/playbooks", json={"app_id": DEMO_APP_ID, "raw_markdown": "no flows"})).status_code == 422

    # Run it and fetch the step screenshot through the artifact route (local fallback store).
    run_id = (await client.post("/runs", json={"app_id": "demo-shop", "mode": "stub", "playbook_id": pb_id})).json()["id"]
    await wait_done(client, run_id)
    item = next(i for i in uploader.items if i["kind"] == "screenshot")
    from qagent.storage.objects import object_store
    monkeypatch.setattr(object_store, "client", None)  # exercise the local-disk fallback
    monkeypatch.setattr(object_store, "local_dir", tmp_path)
    object_store.put_object(item["key"], item["data"], "image/jpeg")  # FakeUploader skips storage
    flow_key = item["key"].split("/flows/")[1].split("/")[0]
    r = await client.get(f"/api/artifacts/{run_id}/flows/{flow_key}/steps/1/screenshot.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_replay_reproduces_run_from_tape(client):
    src = (await client.post("/runs", json={"app_id": "demo-shop", "mode": "stub"})).json()["id"]
    src_run = await wait_done(client, src)

    replay = await client.post(f"/runs/{src}/replay", json={})
    assert replay.status_code == 202, replay.text
    rid = replay.json()["id"]
    assert replay.json()["trigger"] == "replay"
    rerun = await wait_done(client, rid)

    assert rerun["status"] == src_run["status"]
    assert rerun["totals"]["findings_count"] == src_run["totals"]["findings_count"]
    decisions = {e["data"]["payload"]["decider"] for e in parse_sse((await client.get(f"/runs/{rid}/events")).text)
                 if e["event"] == "DECISION_MADE"}
    assert decisions == {"replay"}

    assert (await client.post("/runs/nope/replay", json={})).status_code == 404
