import pytest
from sqlmodel import select

from conftest import PLAYBOOK
from qagent.decision.stub import StubDecider
from qagent.domain.models import FindingRecord
from qagent.domain.runspec import FlowSpec, RunSpec
from qagent.domain.schemas import RunMode
from qagent.engine.findings import Verifier
from qagent.engine.graph import EngineRunner
from qagent.playbooks.parser import parse_playbook_markdown
from qagent.storage.persistence_sink import PersistenceSink


def _spec(run_id, url, only=None):
    parsed = parse_playbook_markdown(PLAYBOOK.read_text())
    flows = [FlowSpec.model_validate(f) for f in parsed["flows"] if only is None or f["key"] in only]
    return RunSpec(run_id=run_id, app_id="app-demo", base_url=url, mode=RunMode.STUB, flows=flows)


async def _run(spec, mem_sessions, uploader):
    sink = PersistenceSink(spec.run_id, session_factory=mem_sessions)
    result = await EngineRunner(spec, StubDecider(), sink, uploader=uploader).run()
    async with mem_sessions() as s:
        findings = (await s.execute(select(FindingRecord))).scalars().all()
    return result, findings


def test_parser_reads_formula_bindings():
    parsed = parse_playbook_markdown(PLAYBOOK.read_text())
    badge = parsed["flows"][0]["formulas"]["cart_badge"]
    assert badge["kind"] == "dom"
    assert badge["bindings"]["badge"] == "ui:[data-testid=cart-badge]"
    assert parsed["flows"][0]["formulas"]["cart_total"]["bindings"]["tax_rate"] == "const:0.08"


def test_verifier_unit_checks():
    assert Verifier.check_timing(1500) is None
    assert Verifier.check_timing(2500).kind.value == "timing"
    assert Verifier.check_network_status(200, "u") is None
    assert Verifier.check_network_status(500, "u").kind.value == "network"
    assert Verifier.check_formula("f", "a == b", {"a": 1, "b": 1}) is None
    assert Verifier.check_formula("f", "a == b", {"a": 1, "b": 2}).kind.value == "formula"
    unbound = Verifier.check_formula("f", "a == missing", {"a": 1})
    assert "could not be evaluated" in unbound.title


@pytest.mark.asyncio
async def test_bug1_badge_mismatch_is_dom_finding(shop, mem_sessions, uploader):
    url, set_bugs = shop
    set_bugs(bug3=False, bug4=False, bug5=False)
    result, findings = await _run(_spec("r-bug1", url, only={"add-to-cart"}), mem_sessions, uploader)
    dom = [f for f in findings if f.kind == "dom"]
    assert len(dom) == 1, [(f.kind, f.title) for f in findings]
    assert dom[0].evidence["context"]["badge"] == 1
    assert [f for f in findings if f.kind == "formula"] == []  # cart_total itself must evaluate cleanly
    assert result["flows"]["add-to-cart"] == "passed_with_findings"


@pytest.mark.asyncio
async def test_bug3_third_payment_is_network_finding(shop, mem_sessions, uploader):
    url, set_bugs = shop
    set_bugs(bug1=False, bug4=False, bug5=False)
    _, findings = await _run(_spec("r-bug3", url, only={"payment"}), mem_sessions, uploader)
    net = [f for f in findings if f.kind == "network"]
    assert len(net) == 1
    assert net[0].actual == "HTTP 500" and net[0].evidence["url"].endswith("/api/pay")
    assert net[0].step_seq == 6


@pytest.mark.asyncio
async def test_bug5_tax_before_discount_is_formula_finding(shop, mem_sessions, uploader):
    url, set_bugs = shop
    set_bugs(bug1=False, bug3=False, bug4=False)
    _, findings = await _run(_spec("r-bug5", url, only={"apply-coupon"}), mem_sessions, uploader)
    formula = [f for f in findings if f.kind == "formula"]
    assert len(formula) == 1 and formula[0].title == "Check failed: discounted_total"
    ctx = formula[0].evidence["context"]
    assert ctx["discount"] == 19.8 and ctx["total"] == 194.04  # tax before discount


@pytest.mark.asyncio
async def test_bug4_spinner_is_unsettled_timing_finding_with_wait_frames(shop, mem_sessions, uploader):
    url, set_bugs = shop
    set_bugs(bug1=False, bug3=False, bug5=False)
    _, findings = await _run(_spec("r-bug4", url, only={"apply-coupon"}), mem_sessions, uploader)
    timing = [f for f in findings if f.kind == "timing"]
    assert len(timing) == 1 and "never settled" in timing[0].title and timing[0].step_seq == 5
    assert len(uploader.keys("wait")) >= 3


@pytest.mark.asyncio
async def test_all_bugs_off_yields_no_findings(shop, mem_sessions, uploader):
    url, set_bugs = shop
    set_bugs(bug1=False, bug2=False, bug3=False, bug4=False, bug5=False)
    result, findings = await _run(_spec("r-clean", url), mem_sessions, uploader)
    assert findings == [], [(f.kind, f.title, f.actual) for f in findings]
    assert result["status"] == "passed"
