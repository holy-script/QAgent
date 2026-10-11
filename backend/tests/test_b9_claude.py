import httpx
import pytest
import respx

from conftest import PLAYBOOK
from qagent.decision.base import Decider
from qagent.decision.claude import BedrockClient, ClaudeDecider
from qagent.domain.runspec import FlowSpec, RunSpec
from qagent.domain.schemas import CandidateAction, ConfidenceTier, DecisionRequest, RunMode, DecisionResult
from qagent.engine.graph import EngineRunner
from qagent.playbooks.normalize import normalize_playbook
from qagent.storage.persistence_sink import PersistenceSink


def _client():
    return BedrockClient(api_key="k", region="us-east-1", model_id="test-model")


def _tool_reply(args, usage=None):
    return httpx.Response(200, json={
        "output": {"message": {"content": [{"toolUse": {"name": "x", "input": args}}]}},
        "usage": usage or {"inputTokens": 1000, "outputTokens": 100},
    })


REQ = DecisionRequest(step_seq=1, intent="Click Pay now", url="http://x/checkout", candidates=[
    CandidateAction(id=1, tag="a", selector="a", label="Home"),
    CandidateAction(id=2, tag="button", selector="button", label="Pay now"),
])


@pytest.mark.asyncio
@respx.mock
async def test_claude_decider_forces_tool_and_prices_tokens():
    route = respx.post(url__regex=r"https://bedrock-runtime\.us-east-1\.amazonaws\.com/model/test-model/converse").mock(
        return_value=_tool_reply({"candidate_id": 2, "confidence": 0.93, "reasoning": "label matches"}))
    res = await ClaudeDecider(_client()).decide(REQ)
    assert (res.decider, res.selected_action_id, res.tier) == ("claude", 2, ConfidenceTier.AUTO)
    assert res.cost_usd == pytest.approx(0.003 + 0.0015)
    sent = route.calls[0].request
    assert sent.headers["authorization"] == "Bearer k"
    assert b'"toolChoice":{"tool":{"name":"choose_action"}}' in sent.content.replace(b" ", b"")


@pytest.mark.asyncio
@respx.mock
async def test_claude_decider_rejects_hallucinated_id_and_retries_429(monkeypatch):
    async def no_sleep(_): pass
    monkeypatch.setattr("qagent.decision.claude.asyncio.sleep", no_sleep)
    respx.post(url__regex=r".*/converse").mock(side_effect=[
        httpx.Response(429), _tool_reply({"candidate_id": 99, "confidence": 0.9, "reasoning": "?"})])
    res = await ClaudeDecider(_client()).decide(REQ)
    assert res.confidence == 0.0 and res.tier == ConfidenceTier.STOP


@pytest.mark.asyncio
@respx.mock
async def test_normalize_playbook_reparses_output():
    md = PLAYBOOK.read_text()
    respx.post(url__regex=r".*/converse").mock(return_value=_tool_reply({"markdown": md, "notes": "none"}))
    out = await normalize_playbook("buy things then pay", _client())
    assert [f["key"] for f in out["parsed"]["flows"]] == ["add-to-cart", "apply-coupon", "payment"]
    assert out["warnings"] == []


class LowConfidence:
    """Primary decider that always picks the wrong element at ESCALATE-tier confidence."""
    async def decide(self, request):
        return DecisionResult(decider="jev", model_version="t", selected_action_id=1, confidence=0.6,
                              tier=ConfidenceTier.ESCALATE)


class Right:
    async def decide(self, request):
        pick = next(c.id for c in request.candidates if "add" in c.label.lower())
        return DecisionResult(decider="claude", model_version="t", selected_action_id=pick, confidence=0.95,
                              tier=ConfidenceTier.AUTO, cost_usd=0.01)


@pytest.mark.asyncio
async def test_escalation_replaces_low_confidence_decision(shop, mem_sessions, uploader):
    url, set_bugs = shop
    for n in (1, 2, 3, 4, 5):
        set_bugs(**{f"bug{n}": False})
    spec = RunSpec(run_id="r-esc", app_id="a", base_url=url, mode=RunMode.HYBRID,
                   flows=[FlowSpec(key="f", steps=["Open /products", "Add item to cart", "Go to /cart"],
                                   formulas={"n": {"expr": "n == 1", "bindings": {"n": "api:/api/cart.count"}}})])
    result = await EngineRunner(spec, LowConfidence(), PersistenceSink("r-esc", session_factory=mem_sessions),
                                uploader=uploader, escalator=Right()).run()
    # Jev alone would have clicked "Home"/nav; escalation clicked Add to Cart, so the cart holds 1 item.
    assert result["status"] == "passed", result
