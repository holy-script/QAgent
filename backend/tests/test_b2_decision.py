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
                "choice": 2,
                "confidence": 0.88,
                "model": "jev-1.13.0",
                "probabilities": {"2": 0.88, "1": 0.12},
                "usage": {"prompt_tokens": 120, "completion_tokens": 8}
            })
        ]
    )

    decider = JevDecider(api_key="mock_test_key")
    res = await decider.decide(sample_request)

    assert route.call_count == 2
    assert res.selected_action_id == 2
    assert res.confidence == 0.88
    assert res.tier == ConfidenceTier.AUTO
    assert res.latency_ms > 0
