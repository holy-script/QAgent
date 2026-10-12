"""Journeys described by a goal: the director chooses each next step from the live page."""
import pytest
from sqlmodel import select

from qagent.decision.ledger import LedgerClient
from qagent.decision.stub import StubDecider
from qagent.domain import models as m
from qagent.domain.runspec import FlowSpec, RunSpec
from qagent.domain.schemas import RunMode
from qagent.engine.graph import EngineRunner
from qagent.playbooks.parser import parse_playbook_markdown
from qagent.checks.edge_cases import expand_flows

from qagent.storage.persistence_sink import PersistenceSink
from test_lifecycle import api  # noqa: F401  (fixture)


class Script:
    """A scripted 'Claude': answers each next_step call from a list, and remembers what it was shown."""
    model_id = "fake"

    def __init__(self, answers):
        self.answers, self.prompts = list(answers), []

    async def converse_tool(self, system, user, tool, max_tokens=512, images=None, timeout=60.0):
        self.prompts.append(user)
        status, intent, why = self.answers.pop(0) if self.answers else ("done", "", "no more answers")
        return {"input": {"status": status, "intent": intent, "why": why}, "usage": {"inputTokens": 500, "outputTokens": 30}}


_counter = iter(range(1000))


def spec(url, goal, **kw):
    flow = FlowSpec(key="shop", goal=goal, severity="high", **kw)
    return RunSpec(run_id=f"g{next(_counter)}", app_id="app-demo", base_url=url, mode=RunMode.HYBRID, flows=[flow], reset_path="/__reset")


async def run(url, mem_sessions, uploader, director, **flow_kw):
    s = spec(url, "Put a product in the cart and open the cart", **flow_kw)
    sink = PersistenceSink(s.run_id, session_factory=mem_sessions)
    result = await EngineRunner(s, StubDecider(), sink, uploader=uploader, director=director).run()
    async with mem_sessions() as ses:
        events = (await ses.execute(select(m.EventRecord).where(m.EventRecord.run_id == s.run_id).order_by(m.EventRecord.seq))).scalars().all()
        run_row = await ses.get(m.Run, s.run_id)
    return result, events, run_row


def intents(events):
    return [e.payload["intent"] for e in events if e.type == "step.observed"]


def failure(events):
    return next((e.payload.get("failure_reason") for e in events if e.type == "flow.finished"), None)


@pytest.mark.asyncio
async def test_director_chooses_each_step_until_the_goal_is_reached(shop, mem_sessions, uploader):
    url, _ = shop
    director = Script([("continue", "Open /products", "start"), ("continue", "Add Wireless Headphones to cart", "add one"),
                       ("continue", "Go to /cart", "open the cart"), ("done", "", "the cart page shows the item")])
    result, events, _ = await run(url, mem_sessions, uploader, director, expect=["The cart shows the item"], test_data={"qty": "1"})
    assert intents(events) == ["Open /products", "Add Wireless Headphones to cart", "Go to /cart"]
    assert result["flows"]["shop"] in ("passed", "passed_with_findings") and failure(events) is None
    # what the director was shown: the goal, the expectations, which test-data fields exist (never their values), the page
    first = director.prompts[0]
    assert "Goal: Put a product in the cart" in first and "The cart shows the item" in first and "qty" in first
    assert "(nothing yet" in first and "Interactive elements:" in first
    assert "Open /products -> " in director.prompts[1] and "Visible text" in director.prompts[1]
    assert len(director.prompts) == 4


@pytest.mark.asyncio
async def test_director_calls_are_on_the_tape_and_in_the_cost(shop, mem_sessions, uploader):
    url, _ = shop
    director = Script([("continue", "Open /products", "x"), ("done", "", "y")])
    _, events, run_row = await run(url, mem_sessions, uploader, director)
    calls = [e.payload for e in events if e.type == "model.call"]
    assert [c["purpose"] for c in calls] == ["director", "director"] and all(c["input_hash"] and c["cost_usd"] > 0 for c in calls)
    assert run_row.totals["director_calls"] == 2 and run_row.totals["director_cost_usd"] == pytest.approx(sum(c["cost_usd"] for c in calls))
    assert run_row.totals["total_cost_usd"] >= run_row.totals["director_cost_usd"]


@pytest.mark.asyncio
async def test_blocked_circling_and_budget_are_reported_as_failures(shop, mem_sessions, uploader):
    url, _ = shop
    _, events, _ = await run(url, mem_sessions, uploader, Script([("continue", "Open /products", "x"), ("blocked", "", "the page shows a server error")]))
    assert "blocked before the goal was reached: the page shows a server error" in failure(events)

    same = ("continue", "Open /products", "again")
    _, events, _ = await run(url, mem_sessions, uploader, Script([same] * 6))
    assert "going in circles" in failure(events)


@pytest.mark.asyncio
async def test_a_goal_journey_needs_ai_and_a_repeat_never_makes_a_call_that_is_not_on_the_tape(shop, mem_sessions, uploader):
    url, _ = shop
    _, events, _ = await run(url, mem_sessions, uploader, None)                      # stub mode: no director
    assert "needs AI" in failure(events)

    sent = []

    async def record(call):
        sent.append(call)
    strict = LedgerClient(Script([("continue", "Open /products", "x")]), record, tape={}, strict=True)   # a repeat with an empty tape
    _, events, _ = await run(url, mem_sessions, uploader, strict)
    assert "could not decide the next step" in failure(events) and sent == []


def test_playbook_format_accepts_a_goal_instead_of_steps():
    md = """# Playbook: Forecast
base_url: http://localhost:8001

## Requirements
### REQ-1: Users can finish the forecast setup
- acceptance: After signing in, a user can complete the setup and see a forecast.
- priority: high

## Flows
### Flow: complete-forecast-setup
- covers: REQ-1
- severity: high

#### Goal
Sign in, then complete the forecast setup wizard and reach the results.

#### Expect
- A forecast is shown

#### Test data
- username: admin
- password: example
"""
    parsed = parse_playbook_markdown(md)
    assert parsed["errors"] == []
    flow = parsed["flows"][0]
    assert flow["goal"] == "Sign in, then complete the forecast setup wizard and reach the results." and flow["steps"] == []
    spec_flow = expand_flows(parsed)[0]
    assert spec_flow.goal and spec_flow.test_data["username"] == "admin"
    assert not [w for w in parsed["warnings"] if "unknown field" in w]
    # neither goal nor steps is still an error
    bad = parse_playbook_markdown(md.replace("#### Goal\nSign in, then complete the forecast setup wizard and reach the results.\n", ""))
    assert any("needs a goal or steps" in e for e in bad["errors"])


GENERATED = """# Playbook: Forecast
base_url: http://localhost:8001

## Requirements
### REQ-1: Users can complete the forecast setup
- acceptance: A signed-in user can finish the setup and see a forecast.
- priority: high

## Edge cases
### EC-1: Wrong password
- applies_to: forecast-setup
- expect: An error says the sign-in failed.
- covers: REQ-1
- test_data: password=wrong

## Flows
### Flow: forecast-setup
- covers: REQ-1
- severity: high

#### Goal
Sign in, then complete the forecast setup and reach the results.

#### Expect
- A forecast is shown

#### Test data
- username: <fill in>
- password: <fill in>
"""


@pytest.mark.asyncio
async def test_prd_becomes_a_high_level_plan_that_flags_missing_test_data(api, monkeypatch):
    from qagent.api.routes import apps as apps_route
    from qagent.playbooks import from_prd
    from test_lifecycle import DEMO_APP_ID

    seen = {}

    class Claude:
        model_id = "fake"

        async def converse_tool(self, system, user, tool, max_tokens=512, images=None, timeout=60.0):
            seen.update(system=system, user=user, max_tokens=max_tokens)
            return {"input": {"markdown": GENERATED, "notes": "the PRD does not say how users register"}, "usage": {}}

    monkeypatch.setattr(from_prd, "BedrockClient", lambda: Claude())
    monkeypatch.setattr(apps_route.settings, "bedrock_api_key", "k")

    r = await api.post(f"/apps/{DEMO_APP_ID}/prd/plan", json={"prd": "Users sign in and complete a forecast setup wizard."})
    assert r.status_code == 200
    body = r.json()
    assert body["markdown"] == GENERATED and body["notes"].startswith("the PRD does not say")
    assert body["flows"][0]["goal"].startswith("Sign in") and body["flows"][0]["steps"] == []
    assert any("fill in the test data for 'forecast-setup': username, password" in w for w in body["warnings"])
    assert "NEVER write a `#### Steps` section" in seen["system"] and "Users sign in and complete" in seen["user"]
    assert "Application address:" in seen["user"] and seen["max_tokens"] >= 8000

    # with no PRD anywhere: a clear message; with the saved PRD: used when none is sent
    await api.patch(f"/apps/{DEMO_APP_ID}", json={"prd_markdown": ""})
    assert (await api.post(f"/apps/{DEMO_APP_ID}/prd/plan", json={})).status_code == 422
    await api.patch(f"/apps/{DEMO_APP_ID}", json={"prd_markdown": "Saved PRD text."})
    assert (await api.post(f"/apps/{DEMO_APP_ID}/prd/plan")).status_code == 200 and "Saved PRD text." in seen["user"]
