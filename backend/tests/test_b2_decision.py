import json
import pytest
import respx
import httpx
from qagent.decision.jev import JevDecider
from qagent.decision.stub import StubDecider
from qagent.decision.tape import RecordingDecider, ReplayDecider
from qagent.domain.schemas import DecisionRequest, CandidateAction, ConfidenceTier


@pytest.fixture
def sample_request() -> DecisionRequest:
    return DecisionRequest(
        step_seq=1,
        intent="Add 2 items to cart",
        url="http://localhost:8001/products",
        candidates=[
            CandidateAction(id=1, tag="a", selector="nav a", label="Home"),
            CandidateAction(id=2, tag="button", selector="button.cart", label="Add to Cart"),
        ]
    )


@pytest.mark.asyncio
async def test_stub_decider(sample_request):
    decider = StubDecider()
    res = await decider.decide(sample_request)
    assert res.selected_action_id == 2  # Matches "Add to Cart"
    assert res.confidence == 0.95
    assert res.tier == ConfidenceTier.AUTO


@pytest.mark.asyncio
async def test_recording_and_replay_decider(sample_request):
    stub = StubDecider()
    recorder = RecordingDecider(stub)
    
    first_res = await recorder.decide(sample_request)
    assert first_res.selected_action_id == 2
    
    tape = recorder.export_tape()
    assert len(tape) == 1
    
    replayer = ReplayDecider(tape)
    replay_res = await replayer.decide(sample_request)
    assert replay_res.decider == "replay"
    assert replay_res.selected_action_id == 2


@pytest.mark.asyncio
@respx.mock
async def test_jev_decider_with_mock_and_retry(sample_request):
    # Mock first 429 then 200
    route = respx.post("https://api.typesafe.ai/v1/systemone").mock(
        side_effect=[
            httpx.Response(429, json={"error": "rate limited"}),
            httpx.Response(200, json={
                "model": "jev-latest",
                "answers": {
                    "next_action": {"type": "choice", "choice": "2", "confidence": 0.88,
                                    "probabilities": {"2": 0.88, "1": 0.12}},
                    "risky": {"type": "noul", "noul": 0.05},
                },
                "usage": {"input_tokens": 120, "output_tokens": 8},
            })
        ]
    )

    decider = JevDecider(api_key="mock_test_key")
    res = await decider.decide(sample_request)

    assert route.call_count == 2
    body = json.loads(route.calls[-1].request.content)
    assert body["questions"]["next_action"]["type"] == "choice"
    assert set(body["questions"]["next_action"]["criteria"]) == {"1", "2", "STEP_DONE", "STUCK"}
    assert body["questions"]["risky"]["type"] == "noul" and "prev_step_ok" not in body["questions"]
    assert res.risky == 0.05 and res.outcome == "act"
    assert res.selected_action_id == 2
    assert res.confidence == 0.88
    assert res.tier == ConfidenceTier.AUTO
    assert res.latency_ms > 0


@pytest.mark.asyncio
async def test_replay_reports_divergence_when_page_differs(sample_request):
    recorder = RecordingDecider(StubDecider())
    await recorder.decide(sample_request)
    tape = {h: {**e, "step_seq": e["request"]["step_seq"], "intent": e["request"]["intent"]}
            for h, e in recorder.export_tape().items()}
    replayer = ReplayDecider(tape)

    changed = sample_request.model_copy(update={"candidates": sample_request.candidates[:1]})
    from qagent.decision.tape import hash_request
    res = await replayer.decide(changed)
    assert res.decider == "replay" and res.selected_action_id == 2  # the recorded choice is still replayed
    div = replayer.take_divergence(hash_request(changed))
    assert div["step_seq"] == 1 and div["expected_hash"] == hash_request(sample_request)
    assert replayer.take_divergence(hash_request(changed)) is None
