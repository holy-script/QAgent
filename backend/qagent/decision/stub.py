from typing import Dict, Any, Optional
from qagent.decision.base import Decider
from qagent.domain.schemas import DecisionRequest, DecisionResult, ConfidenceTier


class StubDecider:
    """Deterministic fast stub decider for offline runs & tests."""

    def __init__(self, forced_action_id: Optional[int] = None, confidence: float = 0.95):
        self.forced_action_id = forced_action_id
        self.confidence = confidence

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        action_id = 1
        if self.forced_action_id is not None:
            action_id = self.forced_action_id
        elif request.candidates:
            # Pick first available or match intent keyword
            intent_lower = request.intent.lower()
            matched = False
            for cand in request.candidates:
                if any(word in cand.label.lower() for word in intent_lower.split() if len(word) > 3):
                    action_id = cand.id
                    matched = True
                    break
            if not matched:
                action_id = request.candidates[0].id

        tier = ConfidenceTier.AUTO if self.confidence >= 0.75 else ConfidenceTier.ESCALATE

        return DecisionResult(
            decider="stub",
            model_version="stub-1.0",
            selected_action_id=action_id,
            confidence=self.confidence,
            tier=tier,
            reasoning=f"Stub selected candidate #{action_id} for step '{request.intent}'",
            probabilities={action_id: self.confidence},
            latency_ms=15.0,
            input_tokens=50,
            output_tokens=10,
            cost_usd=0.0,
        )
