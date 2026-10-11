"""Judge calls on the tape, cost roll-up, and the deterministic browser/target."""
import asyncio

import pytest
from httpx import AsyncClient
from sqlmodel import select

from conftest import FakeJudge
from qagent.browser.sandbox import BrowserSandbox
from qagent.config import settings
from qagent.decision.ledger import LedgerClient, TapedJudge, judge_hash
from test_lifecycle import api, run_and_wait  # noqa: F401  (fixtures and helper)
from qagent.api.seed import DEMO_APP_ID
from qagent.domain import models as m


class CostlyJudge(FakeJudge):
    """Like FakeJudge but reports what a Claude call would cost."""

    async def ask(self, *a, **k):
        v = await super().ask(*a, **k)
        v.cost_usd, v.input_tokens, v.output_tokens, v.model_version = 0.002, 400, 30, "fake-1"
        return v


@pytest.mark.asyncio
async def test_taped_judge_records_then_replays_without_calling_the_model():
    sent = []

    async def emit(call):
        sent.append(call)

    live = TapedJudge(CostlyJudge())
    live.bind(emit)
    first = await live.ask("is there an error?", "Address saved", hints=["x"])
    key = judge_hash("is there an error?", "Address saved", ["x"])
    assert sent[0]["input_hash"] == key and sent[0]["cost_usd"] == 0.002 and not sent[0]["replayed"]

    class Boom:
        async def ask(self, *a, **k):
            raise AssertionError("must be served from the tape")

    replay = TapedJudge(Boom(), tape={key: sent[0]["response"]})
    replay.bind(emit)
    again = await replay.ask("is there an error?", "Address saved", hints=["x"])
    assert again.passed == first.passed and again.reasoning == first.reasoning
    assert sent[1]["replayed"] and sent[1]["cost_usd"] == 0.0  # nothing was paid for

    with pytest.raises(LookupError):
        await TapedJudge(None, tape={}).ask("never seen", "page")


@pytest.mark.asyncio
async def test_ledger_client_records_cost_and_serves_replays():
    rows = []

    async def record(call):
        rows.append(call)

    class Inner:
        model_id = "claude-x"
        calls = 0

        async def converse_tool(self, system, user, tool, max_tokens=512, images=None):
            Inner.calls += 1
            return {"input": {"impact": "i"}, "usage": {"inputTokens": 1000, "outputTokens": 100}}

    tool = {"toolSpec": {"name": "bug_narrative"}}
    out = await LedgerClient(Inner(), record).converse_tool("s", "u", tool)
    assert out["input"] == {"impact": "i"}
    assert rows[0]["purpose"] == "bug_narrative" and rows[0]["cost_usd"] == pytest.approx(0.003 + 0.0015)
    tape = {rows[0]["input_hash"]: rows[0]["response"]}
    await LedgerClient(Inner(), record, tape).converse_tool("s", "u", tool)
    assert Inner.calls == 1 and rows[1]["replayed"] and rows[1].get("cost_usd", 0.0) == 0.0


@pytest.mark.asyncio
async def test_run_puts_judge_calls_on_the_tape_and_in_the_cost(api: AsyncClient):  # noqa: F811
    api.manager.judge_factory = lambda mode: CostlyJudge()
    run_id = await run_and_wait(api, flow_keys=["checkout"], include_edge_cases=True)
    async with api.sessions() as s:
        calls = (await s.execute(select(m.ModelCall).where(m.ModelCall.run_id == run_id))).scalars().all()
        run = await s.get(m.Run, run_id)
    judged = [c for c in calls if c.purpose == "judge"]
    assert judged and all(c.input_hash and c.flow_run_id for c in judged)
    assert run.totals["judge_calls"] == len(judged)
    assert run.totals["judge_cost_usd"] == pytest.approx(0.002 * len(judged))
    assert run.totals["total_cost_usd"] >= run.totals["judge_cost_usd"]


@pytest.mark.asyncio
async def test_repeating_a_run_answers_judgements_from_the_tape(api: AsyncClient):  # noqa: F811
    api.manager.judge_factory = lambda mode: CostlyJudge()
    source = await run_and_wait(api, flow_keys=["checkout"], include_edge_cases=True)
    api.manager.judge_factory = lambda mode: None  # a live judge would be unavailable: only the tape can answer
    replay_id = (await api.post(f"/runs/{source}/replay", json={"overrides": {}})).json()["id"]
    for _ in range(480):
        if replay_id not in api.manager.active:
            break
        await asyncio.sleep(0.25)
    async with api.sessions() as s:
        calls = (await s.execute(select(m.ModelCall).where(m.ModelCall.run_id == replay_id))).scalars().all()
        run = await s.get(m.Run, replay_id)
    assert calls and all(c.replayed and c.cost_usd == 0 for c in calls)
    assert run.totals["judge_cost_usd"] == 0


@pytest.mark.asyncio
async def test_browser_clock_is_fixed_and_animations_are_off(shop):
    module, _ = shop
    sandbox = BrowserSandbox(headless=True)
    page = await sandbox.start()
    try:
        await page.goto("data:text/html,<div id=a style='transition:all 1s'>x</div>")
        now = await page.evaluate("new Date().toISOString()")
        assert now.startswith(settings.fixed_clock_iso[:10])
        assert await page.evaluate("getComputedStyle(document.getElementById('a')).transitionDuration") == "0s"
    finally:
        await sandbox.stop()


@pytest.mark.asyncio
async def test_planner_notes_reach_step_decisions_and_cost_is_counted(shop, mem_sessions, uploader):
    from qagent.decision.stub import StubDecider
    from qagent.engine.graph import EngineRunner
    from qagent.storage.persistence_sink import PersistenceSink
    from test_b6_findings import spec_for

    url, _ = shop
    seen = []

    class Capturing(StubDecider):
        async def decide(self, request):
            seen.append((request.step_seq, list(request.hints)))
            return await super().decide(request)

    class Planner:
        model_id = "claude-x"

        async def converse_tool(self, system, user, tool, max_tokens=512, images=None):
            return {"input": {"summary": "adds a mug", "steps": [
                {"step": 2, "look_for": "an Add button", "caution": "two products look alike"},
                {"step": 99, "look_for": "ignored: no such step"}]},
                "usage": {"inputTokens": 1000, "outputTokens": 100}}

    spec = spec_for("rp", url, ["add-to-cart"], edge=False, plan=True)
    sink = PersistenceSink(spec.run_id, session_factory=mem_sessions)
    result = await EngineRunner(spec, Capturing(), sink, uploader=uploader, planner=Planner()).run()
    assert result["status"] in ("passed", "failed")
    assert any("Look for: an Add button" in h and "two products look alike" in h for seq, hints in seen if seq == 2 for h in hints)
    assert not any("ignored" in h for _, hints in seen for h in hints)
    async with mem_sessions() as s:
        calls = (await s.execute(select(m.ModelCall).where(m.ModelCall.run_id == "rp"))).scalars().all()
        run = await s.get(m.Run, "rp")
    assert [c.purpose for c in calls] == ["planner"] and calls[0].cost_usd > 0
    assert run.totals["planner_cost_usd"] == pytest.approx(calls[0].cost_usd)


@pytest.mark.asyncio
async def test_tape_endpoint_lists_decisions_judgements_and_cost(api: AsyncClient):  # noqa: F811
    api.manager.judge_factory = lambda mode: CostlyJudge()
    run_id = await run_and_wait(api, flow_keys=["checkout"], include_edge_cases=True)
    tape = (await api.get(f"/runs/{run_id}/tape")).json()
    kinds = {e["kind"] for e in tape}
    assert {"decision", "judge"} <= kinds
    assert [e["phase"] for e in tape] == sorted(e["phase"] for e in tape)
    assert all(e["flow_key"] for e in tape if e["kind"] in ("decision", "judge"))
    assert sum(e["cost_usd"] for e in tape if e["kind"] == "judge") == pytest.approx(
        (await api.get(f"/runs/{run_id}")).json()["totals"]["judge_cost_usd"])
    assert (await api.get("/runs/nope/tape")).status_code == 404
