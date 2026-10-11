import pytest
from sqlmodel import select

from conftest import PLAYBOOK
from qagent.decision.stub import StubDecider
from qagent.domain.models import Decision, EventRecord, FlowRun, Run, Step, StepTiming
from qagent.domain.runspec import FlowSpec, RunSpec
from qagent.domain.schemas import RunMode
from qagent.engine.graph import EngineRunner, parse_navigation, repeat_count, resolve_fill_value
from qagent.domain.schemas import CandidateAction
from qagent.playbooks.parser import parse_playbook_markdown
from qagent.storage.persistence_sink import PersistenceSink


def test_step_intent_helpers():
    assert parse_navigation("Open /products") == "/products"
    assert parse_navigation("Go to /cart") == "/cart"
    assert parse_navigation("Open the menu") is None
    assert repeat_count("Add 2 items to cart") == 2
    assert repeat_count("Add item to cart") == 1
    assert repeat_count("Click Pay now") == 1
    cand = CandidateAction(id=1, tag="input", selector="#coupon", label="Coupon Code", action_type="fill")
    assert resolve_fill_value("Enter the coupon code", cand, {"coupon": "SAVE10"}) == "SAVE10"
    assert resolve_fill_value('Type "ABC" in the field', cand, {}) == "ABC"


@pytest.mark.asyncio
async def test_engine_runs_clean_flow_and_persists_rows(shop, mem_sessions, uploader):
    url, set_bugs = shop
    set_bugs(bug1=False, bug2=False, bug3=False, bug4=False, bug5=False)
    spec = RunSpec(
        run_id="run-clean", app_id="app-demo", base_url=url, mode=RunMode.STUB,
        flows=[FlowSpec(key="browse", steps=["Open /products", "Add 2 items to cart", "Go to /cart"])],
    )
    sink = PersistenceSink("run-clean", session_factory=mem_sessions)
    result = await EngineRunner(spec, StubDecider(), sink, uploader=uploader).run()

    assert result["status"] == "passed", result
    assert result["total_steps"] == 3

    async with mem_sessions() as s:
        run = await s.get(Run, "run-clean")
        assert run.status == "passed" and run.totals["total_steps"] == 3
        flows = (await s.execute(select(FlowRun))).scalars().all()
        assert [f.status for f in flows] == ["passed"]
        steps = (await s.execute(select(Step).order_by(Step.seq))).scalars().all()
        assert [st.status for st in steps] == ["passed"] * 3
        assert len((await s.execute(select(StepTiming))).scalars().all()) == 3
        decisions = (await s.execute(select(Decision))).scalars().all()
        assert len(decisions) == 1  # only "Add 2 items" needs a model; navigation is deterministic
        assert len((await s.execute(select(EventRecord))).scalars().all()) == sink._seq

    assert any(k.endswith("steps/2/screenshot.jpg") for k in uploader.keys("screenshot"))
    assert uploader.keys("trace") and uploader.keys("har")


@pytest.mark.asyncio
async def test_engine_blocks_disallowed_host(shop, mem_sessions, uploader):
    url, _ = shop
    spec = RunSpec(
        run_id="run-host", app_id="app-demo", base_url=url, mode=RunMode.STUB,
        flows=[FlowSpec(key="escape", steps=["Open http://example.com/"])],
    )
    result = await EngineRunner(
        spec, StubDecider(), PersistenceSink("run-host", session_factory=mem_sessions), uploader=uploader
    ).run()
    assert result["status"] == "failed"
    assert result["flows"]["escape"] == "failed"


@pytest.mark.asyncio
async def test_graph_topology_checkpoints_and_node_spans(shop, mem_sessions, uploader):
    url, set_bugs = shop
    for n in (1, 2, 3, 4, 5):
        set_bugs(**{f"bug{n}": False})
    spec = RunSpec(
        run_id="run-lg", app_id="app-demo", base_url=url, mode=RunMode.STUB,
        flows=[FlowSpec(key="browse", steps=["Open /products", "Add item to cart", "Go to /cart"])],
    )
    runner = EngineRunner(spec, StubDecider(), PersistenceSink("run-lg", session_factory=mem_sessions),
                          uploader=uploader)

    nodes = set(runner.graph.get_graph().nodes)
    assert {"plan", "begin_step", "observe", "decide", "gate", "escalate", "act", "settle", "verify",
            "finish"} <= nodes

    result = await runner.run()
    assert result["status"] == "passed"

    # Every super-step was checkpointed under the flow's thread; the last state is the finished flow.
    threads = {c.config["configurable"]["thread_id"] async for c in runner.checkpointer.alist(None)}
    assert len(threads) == 1
    snapshot = await runner.graph.aget_state({"configurable": {"thread_id": threads.pop()}})
    assert snapshot.values["done"] is True and snapshot.values["steps_run"] == 3
    assert [h["status"] for h in snapshot.values["history"]] == ["passed"] * 3

    # LangChain callbacks produced node and model spans nested under the flow span.
    from qagent.domain.models import SpanRecord
    async with mem_sessions() as s:
        spans = (await s.execute(select(SpanRecord))).scalars().all()
    by_name = {}
    for sp in spans:
        by_name.setdefault(sp.name, []).append(sp)
    assert len(by_name["act"]) == 3 and len(by_name["verify"]) == 3 and len(by_name["decide"]) == 1
    assert by_name["model:StubDecider"][0].kind == "model"
    assert by_name["model:StubDecider"][0].parent_span_id == by_name["decide"][0].span_id
    flow_span = by_name["flow:browse"][0]
    assert by_name["act"][0].parent_span_id == flow_span.span_id
