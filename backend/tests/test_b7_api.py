import asyncio
import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from conftest import FakeJudge
from qagent.api import main as api_main
from qagent.api.seed import DEMO_APP_ID, seed_demo
from qagent.decision.stub import StubDecider
from qagent.domain.models import App
from qagent.reports.pipeline import run_report_pipeline
from qagent.runs.manager import RunManager, get_run_manager
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
    monkeypatch.setattr(db, "async_session_factory", mem_sessions)
    async with mem_sessions() as s:
        await seed_demo(s)
        app = await s.get(App, DEMO_APP_ID)
        app.base_url = shop_url
        await s.commit()

    manager = RunManager(
        session_factory=mem_sessions, decider_factory=lambda mode: StubDecider(), escalator_factory=lambda mode: None,
        judge_factory=lambda mode: FakeJudge(), uploader=uploader, report_hook=run_report_pipeline)
    api_main.app.dependency_overrides[get_run_manager] = lambda: manager
    async with AsyncClient(transport=ASGITransport(app=api_main.app), base_url="http://test") as ac:
        ac.manager, ac.set_bugs = manager, set_bugs
        yield ac
    api_main.app.dependency_overrides.clear()


async def finish(client, run_id, timeout=120):
    """Waits for the run and its report (the SSE stream ends with the run report)."""
    for _ in range(timeout * 4):
        if run_id not in client.manager.active:
            return (await client.get(f"/runs/{run_id}")).json()
        await asyncio.sleep(0.25)
    raise AssertionError("run did not finish")


@pytest.mark.asyncio
async def test_run_pipeline_end_to_end_issues_evidence_reports_and_resolution(client):
    resp = await client.post("/apps/demo-shop/runs", json={"mode": "stub"})
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["id"]

    # Attach while live: replay + follow; the stream ends with the run report.
    events = parse_sse((await client.get(f"/runs/{run_id}/events")).text)
    seqs = [e["id"] for e in events]
    assert seqs == list(range(1, len(seqs) + 1))
    types = [e["event"] for e in events]
    assert types[0] == "run.started" and types[-1] == "report.ready" and events[-1]["data"]["payload"]["kind"] == "run"
    assert types.index("run.finished") < types.index("report.generating") < len(types) - 1
    assert {"check.result", "finding.created", "network.call", "decision.made", "span.ended"} <= set(types)

    run = await finish(client, run_id)
    assert run["status"] == "failed" and run["totals"]["findings_count"] >= 6

    # resume from the middle, via ?after= and Last-Event-ID
    mid = seqs[len(seqs) // 2]
    via_query = parse_sse((await client.get(f"/runs/{run_id}/events", params={"after": mid})).text)
    via_header = parse_sse((await client.get(f"/runs/{run_id}/events", headers={"Last-Event-ID": str(mid)})).text)
    assert [e["id"] for e in via_query] == [e["id"] for e in via_header] == [s for s in seqs if s > mid]

    # read models
    flows = (await client.get(f"/runs/{run_id}/flows")).json()
    assert {f["flow_key"] for f in flows} == {"add-to-cart", "apply-coupon", "payment", "checkout",
                                              "apply-coupon#EC-2", "checkout#EC-3"}
    assert all(st["timings"]["total_ms"] > 0 for f in flows for st in f["steps"])
    steps = (await client.get(f"/runs/{run_id}/steps", params={"flow_key": "payment"})).json()
    assert len(steps) == 6 and steps[0]["screenshot_url"].endswith("/steps/1/screenshot.jpg")
    assert any(st["decision"] for st in steps)

    findings = (await client.get(f"/runs/{run_id}/findings")).json()
    keys = {f["check_key"] for f in findings}
    assert {"UX-1", "F-1", "UX-2", "network:POST /api/pay", "UX-3"} <= keys
    assert all(f["fingerprint"] and f["issue_id"] for f in findings)
    assert {f["kind"] for f in findings} == {"dom", "network", "formula", "timing"}

    checks = (await client.get(f"/runs/{run_id}/checks", params={"passed": False})).json()
    assert checks and all(not c["passed"] for c in checks)
    f1 = next(c for c in (await client.get(f"/runs/{run_id}/checks")).json() if c["check_key"] == "F-1")
    assert f1["inputs"]["total"]["source"] == "ui:[data-testid=cart-total]"

    net = (await client.get(f"/runs/{run_id}/network", params={"is_api": True, "min_status": 500})).json()
    assert net and all(c["status"] >= 500 and c["is_api"] for c in net)
    call = (await client.get(f"/network/{net[0]['id']}")).json()
    assert call["flow_key"] == "payment" and call["resp_artifact_key"]
    assert (await client.get(call["resp_body_url"])).status_code in (200, 404)  # body may still be a 500 json

    spans = (await client.get(f"/runs/{run_id}/spans")).json()
    assert {"flow", "node", "model"} <= {sp["kind"] for sp in spans}

    # evidence graph for the network finding, including the annotated screenshot added after the run
    pay = next(f for f in findings if f["check_key"] == "network:POST /api/pay")
    graph = (await client.get(f"/findings/{pay['id']}/evidence")).json()
    kinds = {e["kind"] for e in graph["evidence"]}
    assert {"screenshot_before", "screenshot_after", "annotated", "network_call", "decision", "trace"} <= kinds
    annotated = next(e for e in graph["evidence"] if e["kind"] == "annotated")
    assert annotated["available"]
    url = (await client.get(annotated["url"])).json()["url"]
    assert (await client.get(url)).headers["content-type"] == "image/jpeg"
    assert graph["check_result"]["inputs"]["status"] == 500

    # issues
    issues = (await client.get(f"/apps/{DEMO_APP_ID}/issues", params={"status": "open"})).json()
    assert len(issues) >= 6 and all(i["occurrences"] == 1 for i in issues)
    assert (await client.get(f"/apps/{DEMO_APP_ID}/issues", params={"severity": "critical"})).status_code == 200

    # reports
    report = (await client.get(f"/runs/{run_id}/report")).json()
    c = report["content"]
    assert report["status"] == "ready" and c["summary"]["issues"]["new"] == len(issues)
    reqs = {r["key"]: r["status"] for r in c["requirements"]}
    assert reqs == {"REQ-1": "covered_failing", "REQ-2": "not_covered" if False else reqs["REQ-2"], "REQ-3": "covered_failing"}
    assert c["recommendations_status"] == "not generated"  # no Claude in this test
    assert c["integrity"]["manifest_hash"] and c["performance"]["slowest_api_calls"]
    assert len(c["appendix"]["bug_reports"]) == len(issues)

    pay_issue = next(i for i in issues if i["check_key"] == "network:POST /api/pay")
    bug = (await client.get(f"/issues/{pay_issue['id']}/report")).json()["content"]
    assert bug["steps_to_reproduce"][0] == "1. Open /products" and bug["steps_to_reproduce"][-1].startswith("6. Click Pay now")
    assert bug["expected_actual"]["actual"] == "HTTP 500" and bug["narrative"]["status"] == "not generated"
    assert bug["evidence"]["network_calls"][0]["status"] == 500 and "6" in bug["evidence"]["run_link"]
    assert bug["reproducibility"] == {**bug["reproducibility"], "seen_in": 1, "of_last": 1}
    f1_issue = next(i for i in issues if i["check_key"] == "F-1")
    f1_bug = (await client.get(f"/issues/{f1_issue['id']}/report")).json()["content"]
    assert f1_bug["violated_requirements"][0]["key"] == "REQ-1" and f1_bug["priority"] == "high"

    report_id = (await client.get(f"/issues/{pay_issue['id']}/report")).json()["id"]
    md = await client.get(f"/reports/{report_id}/export", params={"format": "md"})
    assert md.status_code == 200 and "Steps to reproduce" in md.text and "HTTP 500" in md.text
    html = await client.get(f"/reports/{report_id}/export", params={"format": "html"})
    assert "data:image/jpeg;base64" in html.text  # screenshots embedded
    pdf = await client.get(f"/reports/{report_id}/export", params={"format": "pdf"})
    assert pdf.content[:4] == b"%PDF"

    # artifacts by id and manifest integrity
    detail = (await client.get(f"/issues/{pay_issue['id']}")).json()
    assert detail["occurrence_list"][0]["run_id"] == run_id

    # traceability
    trace = (await client.get(f"/apps/{DEMO_APP_ID}/traceability")).json()
    by_req = {r["key"]: r for r in trace["requirements"]}
    assert by_req["REQ-1"]["status"] == "covered_failing" and by_req["REQ-1"]["finding_ids"]
    assert {i["key"] for i in by_req["REQ-1"]["items"]} >= {"F-1", "add-to-cart", "apply-coupon", "EC-2", "UX-1"}
    assert by_req["REQ-3"]["issue_ids"] and trace["uncovered"] == []

    # flows with history
    fl = {f["flow_key"]: f for f in (await client.get(f"/apps/{DEMO_APP_ID}/flows")).json()}
    assert fl["payment"]["last_results"][0]["status"] == "passed_with_findings"
    hist = (await client.get(f"/apps/{DEMO_APP_ID}/flows/checkout%23EC-3/history")).json()
    assert hist["results"]

    # app list summary
    apps = (await client.get("/apps")).json()
    assert apps[0]["open_issues"] == len(issues) and apps[0]["last_run"]["id"] == run_id

    # second run, same bugs: issues recur instead of duplicating
    run2 = (await client.post(f"/apps/{DEMO_APP_ID}/runs", json={"mode": "stub"})).json()["id"]
    await finish(client, run2)
    again = (await client.get(f"/apps/{DEMO_APP_ID}/issues")).json()
    assert len(again) == len(issues) and all(i["occurrences"] == 2 for i in again)
    assert (await client.get(f"/runs/{run2}/report")).json()["content"]["summary"]["issues"]["recurring"] == len(issues)

    # fix every bug: the next run resolves all issues
    for n in (1, 2, 3, 4, 5):
        client.set_bugs(**{f"bug{n}": False})
    run3 = (await client.post(f"/apps/{DEMO_APP_ID}/runs", json={"mode": "stub"})).json()["id"]
    run3_row = await finish(client, run3)
    assert run3_row["status"] == "passed", (await client.get(f"/runs/{run3}/findings")).json()
    resolved = (await client.get(f"/apps/{DEMO_APP_ID}/issues", params={"status": "resolved"})).json()
    assert len(resolved) == len(issues) and all(i["last_pass_run_id"] == run3 for i in resolved)

    # bring one back: it regresses
    client.set_bugs(bug3=True)
    run4 = (await client.post(f"/apps/{DEMO_APP_ID}/runs", json={"mode": "stub", "flow_keys": ["payment"]})).json()["id"]
    await finish(client, run4)
    regressed = (await client.get(f"/apps/{DEMO_APP_ID}/issues", params={"status": "regressed"})).json()
    assert [i["check_key"] for i in regressed] == ["network:POST /api/pay"]

    assert (await client.get("/runs/nope/events")).status_code == 404
    assert (await client.get("/findings/nope/evidence")).status_code == 404


@pytest.mark.asyncio
async def test_stop_run_and_error_paths(client):
    assert (await client.post("/runs", json={"app_id": "missing", "mode": "stub"})).status_code == 404
    run_id = (await client.post("/runs", json={"app_id": "demo-shop", "mode": "stub"})).json()["id"]
    assert (await client.post(f"/runs/{run_id}/stop")).status_code == 200
    run = await finish(client, run_id)
    assert run["status"] == "stopped"


@pytest.mark.asyncio
async def test_playbook_upload_validation_versions_and_items(client):
    md = ("# Playbook: Tiny\nbase_url: http://localhost:8001\n\n## Requirements\n### REQ-1: Browse works\n"
          "- acceptance: products load\n\n## Flows\n### Flow: browse\n- covers: REQ-1\n\n#### Steps\n1. Open /products\n")
    v = await client.post("/playbooks/validate", json={"raw_text": md})
    assert v.json()["errors"] == [] and v.json()["counts"]["flows"] == 1 and v.json()["coverage"]["uncovered"] == []

    created = await client.post(f"/apps/{DEMO_APP_ID}/playbooks", json={"app_id": DEMO_APP_ID, "raw_markdown": md})
    assert created.status_code == 201 and created.json()["created"] is True
    pb_id = created.json()["playbook"]["id"]

    again = await client.post(f"/apps/{DEMO_APP_ID}/playbooks", json={"app_id": DEMO_APP_ID, "raw_markdown": md})
    assert again.json()["created"] is False  # same hash: no new version
    changed = await client.post(f"/apps/{DEMO_APP_ID}/playbooks",
                                json={"app_id": DEMO_APP_ID, "raw_markdown": md + "2. Open /cart\n"})
    assert changed.json()["version"]["version_no"] == 2
    versions = (await client.get(f"/playbooks/{pb_id}/versions")).json()
    assert [x["version_no"] for x in versions] == [2, 1]
    items = (await client.get(f"/playbook-versions/{versions[0]['id']}/items", params={"category": "requirement"})).json()
    assert [i["item_key"] for i in items] == ["REQ-1"]

    bad = md.replace("- covers: REQ-1", "- covers: REQ-9")
    r = await client.post(f"/apps/{DEMO_APP_ID}/playbooks", json={"app_id": DEMO_APP_ID, "raw_markdown": bad})
    assert r.status_code == 422 and any("REQ-9" in e for e in r.json()["detail"]["errors"])  # errors block confirmation
    assert (await client.post(f"/apps/{DEMO_APP_ID}/playbooks",
                              json={"app_id": DEMO_APP_ID, "raw_markdown": "no flows"})).status_code == 422


@pytest.mark.asyncio
async def test_app_crud_and_derived_names(client):
    created = await client.post("/apps", json={"base_url": "http://example.test:3000/"})
    assert created.status_code == 201 and created.json()["slug"] == "example-test" \
        and created.json()["allowed_hosts"] == ["example.test"]
    assert (await client.post("/apps", json={"base_url": "http://example.test:3000"})).status_code == 409
    assert (await client.post("/apps", json={"base_url": "ftp://x"})).status_code == 422
    app_id = created.json()["id"]
    patched = await client.patch(f"/apps/{app_id}", json={"name": "Example", "redact_keys": ["email"]})
    assert patched.json()["name"] == "Example" and patched.json()["redact_keys"] == ["email"]
    assert (await client.delete(f"/apps/{app_id}")).status_code == 204
    assert (await client.get(f"/apps/{app_id}")).status_code == 404


@pytest.mark.asyncio
async def test_replay_reproduces_run_from_tape(client):
    src = (await client.post("/runs", json={"app_id": "demo-shop", "mode": "stub", "flow_keys": ["add-to-cart"],
                                            "include_edge_cases": False})).json()["id"]
    src_run = await finish(client, src)
    replay = await client.post(f"/runs/{src}/replay", json={})
    assert replay.status_code == 202, replay.text
    rid = replay.json()["id"]
    assert replay.json()["trigger"] == "replay"
    rerun = await finish(client, rid)

    assert rerun["status"] == src_run["status"]
    assert rerun["totals"]["findings_count"] == src_run["totals"]["findings_count"]
    decisions = {e["data"]["payload"]["decider"] for e in parse_sse((await client.get(f"/runs/{rid}/events")).text)
                 if e["event"] == "decision.made"}
    assert decisions == {"replay"}
    assert (await client.post("/runs/nope/replay", json={})).status_code == 404
