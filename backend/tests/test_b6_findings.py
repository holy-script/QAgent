import httpx
import pytest
from sqlmodel import select

from conftest import PLAYBOOK, FakeJudge
from qagent.checks import timing, ux_rules
from qagent.checks.base import max_severity
from qagent.checks.edge_cases import expand_flows, spec_items
from qagent.decision.stub import StubDecider
from qagent.domain.models import CheckResult, EvidenceLink, FindingRecord
from qagent.domain.runspec import RunSpec
from qagent.domain.schemas import RunMode
from qagent.engine.graph import EngineRunner
from qagent.playbooks.parser import parse_playbook_markdown
from qagent.reports.findings import final_severity, fingerprint
from qagent.storage.persistence_sink import PersistenceSink


def spec_for(run_id, url, only=None, edge=True, **kw):
    parsed = parse_playbook_markdown(PLAYBOOK.read_text())
    return RunSpec(run_id=run_id, app_id="app-demo", base_url=url, mode=RunMode.STUB,
                   flows=expand_flows(parsed, only, edge), reset_path="/__reset", **spec_items(parsed), **kw)


async def run(spec, mem_sessions, uploader, judge=None):
    sink = PersistenceSink(spec.run_id, session_factory=mem_sessions)
    result = await EngineRunner(spec, StubDecider(), sink, uploader=uploader, judge=judge).run()
    async with mem_sessions() as s:
        findings = (await s.execute(select(FindingRecord))).scalars().all()
        checks = (await s.execute(select(CheckResult))).scalars().all()
    return result, findings, checks


def test_check_unit_behaviour():
    assert timing.network_check({"method": "GET", "url": "http://h/api/x", "status": 200, "duration_ms": 5}).passed
    bad = timing.network_check({"method": "POST", "url": "http://h/api/pay/42", "status": 500, "duration_ms": 5})
    assert not bad.passed and bad.key == "network:POST /api/pay/:id" and bad.locus == "POST /api/pay/:id"
    assert timing.network_check({"method": "POST", "url": "http://h/api/c", "status": 400, "duration_ms": 5},
                                flow_expects_error=True).passed
    assert timing.slow_call_check({"method": "GET", "url": "http://h/a", "duration_ms": 1500}, 2000) is None
    assert timing.slow_call_check({"method": "GET", "url": "http://h/a", "duration_ms": 2500}, 2000).kind == "timing"
    rule = {"key": "UX-2", "max_ms": "2500"}
    assert ux_rules.max_wait(rule, [{"step_seq": 1, "settle_ms": 100, "settled": True}]).passed
    late = ux_rules.max_wait(rule, [{"step_seq": 5, "settle_ms": 3100, "settled": False}])
    assert not late.passed and late.evidence["step_seq"] == 5
    assert ux_rules.no_console_errors({"key": "U"}, [{"type": "error", "text": "boom"}], []).passed is False
    assert ux_rules.no_console_errors({"key": "U"}, [{"type": "error", "text": "boom"}], ["boo"]).passed is True


def test_severity_and_fingerprint_rules():
    assert max_severity("low", "high") == "high"
    assert final_severity("medium", ["critical"], judged=False) == "critical"
    assert final_severity("medium", ["critical"], judged=True) == "medium"  # judged findings cap at medium
    a = fingerprint("F-1", "checkout#EC-3", "formula", "sel")
    assert a == fingerprint("F-1", "checkout", "formula", "sel")  # variants share the base flow's identity
    assert a != fingerprint("F-1", "checkout", "dom", "sel")


@pytest.mark.asyncio
async def test_bug1_cart_badge_inconsistency(shop, mem_sessions, uploader):
    url, set_bugs = shop
    set_bugs(bug3=False, bug4=False, bug5=False)
    result, findings, checks = await run(spec_for("r1", url, ["add-to-cart"], edge=False), mem_sessions, uploader)
    assert [(f.check_key, f.kind) for f in findings] == [("UX-1", "dom")], [(f.check_key, f.title) for f in findings]
    f = findings[0]
    assert f.fingerprint and f.check_result_id and f.severity == "medium"
    ux1 = next(c for c in checks if c.check_key == "UX-1")
    assert [ux1.inputs[k]["value"] for k in ("target_1", "target_2")] == [1, 2]  # badge 1 vs API count 2
    status = {c.check_key: c.passed for c in checks}
    assert status["F-1"] is True and status["UX-4"] is True
    assert result["flows"]["add-to-cart"] == "passed_with_findings"


@pytest.mark.asyncio
async def test_bug3_third_payment_network_finding_with_evidence(shop, mem_sessions, uploader):
    url, set_bugs = shop
    set_bugs(bug1=False, bug4=False, bug5=False)
    _, findings, _ = await run(spec_for("r3", url, ["payment"], edge=False), mem_sessions, uploader)
    assert len(findings) == 1
    f = findings[0]
    assert (f.kind, f.actual, f.step_seq, f.severity) == ("network", "HTTP 500", 6, "high")
    assert f.check_key == "network:POST /api/pay" and f.requirement_keys == []
    async with mem_sessions() as s:
        links = (await s.execute(select(EvidenceLink).where(EvidenceLink.finding_id == f.id))).scalars().all()
    kinds = {l.kind for l in links}
    assert {"screenshot_before", "screenshot_after", "dom", "trace", "network_call", "decision", "span"} <= kinds
    assert any(l.ref_id.endswith("steps/6/after.jpg") for l in links)


@pytest.mark.asyncio
async def test_bug5_formula_finding_traces_inputs_to_network_call(shop, mem_sessions, uploader):
    url, set_bugs = shop
    set_bugs(bug1=False, bug3=False, bug4=False)
    _, findings, checks = await run(spec_for("r5", url, ["apply-coupon"], edge=False), mem_sessions, uploader)
    assert [f.check_key for f in findings] == ["F-1"]
    f = findings[0]
    assert f.requirement_keys == ["REQ-1"] and f.severity == "high"  # REQ-1 priority
    c = next(c for c in checks if c.check_key == "F-1")
    assert c.inputs["discount"]["value"] == 19.8 and c.inputs["total"]["value"] == 194.04
    assert c.inputs["discount"]["call_id"] and c.inputs["items"]["source"] == "api:/api/cart.items"
    assert c.inputs["total"]["page_url"].endswith("/cart") and c.inputs["total"]["bbox"]
    async with mem_sessions() as s:
        links = (await s.execute(select(EvidenceLink).where(EvidenceLink.finding_id == f.id))).scalars().all()
    assert c.inputs["discount"]["call_id"] in {l.ref_id for l in links if l.kind == "network_call"}


@pytest.mark.asyncio
async def test_bug4_spinner_violates_max_wait_with_wait_frames(shop, mem_sessions, uploader):
    url, set_bugs = shop
    set_bugs(bug1=False, bug3=False, bug5=False)
    _, findings, _ = await run(spec_for("r4", url, ["apply-coupon"], edge=False), mem_sessions, uploader)
    # UX-2 is the defect; F-1 also fires because the UI total was never refreshed (stale vs the API).
    assert [(f.check_key, f.kind, f.step_seq) for f in findings if f.check_key == "UX-2"] == [("UX-2", "timing", 5)]
    assert {f.check_key for f in findings} == {"UX-2", "F-1"}
    assert len(uploader.keys("wait_frame")) >= 3
    async with mem_sessions() as s:
        links = (await s.execute(select(EvidenceLink).where(EvidenceLink.finding_id == findings[0].id))).scalars().all()
    assert sum(l.kind == "wait_frame" for l in links) >= 3


@pytest.mark.asyncio
async def test_bug2_missing_validation_found_by_judged_edge_case(shop, mem_sessions, uploader):
    url, set_bugs = shop
    set_bugs(bug1=False, bug3=False, bug4=False, bug5=False)
    result, findings, checks = await run(
        spec_for("r2", url, ["checkout"]), mem_sessions, uploader, judge=FakeJudge())
    assert sorted(f.check_key for f in findings) == ["UX-3", "expect:checkout#EC-3:1"]
    assert all(f.judged_by == "jev" and f.severity == "medium" for f in findings)  # judged => capped at medium
    assert "expect:checkout:1" in {c.check_key for c in checks} and result["flows"]["checkout"] == "passed"
    ec3 = next(f for f in findings if f.check_key.startswith("expect:"))
    assert "REQ-3" in ec3.requirement_keys

    set_bugs(bug2=False)  # with validation in place, the edge case passes
    _, findings, _ = await run(spec_for("r2b", url, ["checkout"]), mem_sessions, uploader, judge=FakeJudge())
    assert [f.check_key for f in findings if f.run_id == "r2b"] == []


@pytest.mark.asyncio
async def test_expired_coupon_edge_case_400_is_not_a_network_finding(shop, mem_sessions, uploader):
    url, set_bugs = shop
    for n in (1, 2, 3, 4, 5):
        set_bugs(**{f"bug{n}": False})
    _, findings, checks = await run(spec_for("r6", url, ["apply-coupon"]), mem_sessions, uploader, judge=FakeJudge())
    assert findings == [], [(f.check_key, f.actual) for f in findings]
    coupon = next(c for c in checks if c.check_key == "network:POST /api/coupon" and c.actual == "HTTP 400")
    assert coupon.passed is True  # the 400 is recorded, but expected for the EC-2 variant


@pytest.mark.asyncio
async def test_all_bugs_off_full_playbook_is_clean(shop, mem_sessions, uploader):
    url, set_bugs = shop
    for n in (1, 2, 3, 4, 5):
        set_bugs(**{f"bug{n}": False})
    result, findings, _ = await run(spec_for("rc", url), mem_sessions, uploader, judge=FakeJudge())
    assert findings == [], [(f.check_key, f.actual) for f in findings]
    assert result["status"] == "passed" and set(result["flows"]) == {
        "add-to-cart", "apply-coupon", "payment", "checkout", "apply-coupon#EC-2", "checkout#EC-3"}


@pytest.mark.asyncio
async def test_traceparent_is_injected_and_recorded(shop, mem_sessions, uploader):
    url, set_bugs = shop
    set_bugs(bug1=False, bug3=False, bug4=False, bug5=False)
    spec = spec_for("rt", url, ["add-to-cart"], edge=False, inject_traceparent=True)
    await run(spec, mem_sessions, uploader)
    seen = httpx.get(f"{url}/__traces").json()["traces"]
    assert seen and all(t["traceparent"].startswith("00-") and t["traceparent"].endswith("-01") for t in seen)
    from qagent.domain.models import NetworkCallRecord
    async with mem_sessions() as s:
        calls = (await s.execute(select(NetworkCallRecord))).scalars().all()
    assert any(c.traceparent and c.traceparent in {t["traceparent"] for t in seen} for c in calls)
