import re
from typing import Dict, Any, Optional
from qagent.decision.base import Decider
from qagent.domain.schemas import DecisionRequest, DecisionResult, ConfidenceTier


_STOPWORDS = {"the", "and", "click", "open", "press", "tap", "item", "items", "into", "with", "field"}


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
            # Best word overlap between the intent and the candidate label wins; ties go to the first.
            words = {w for w in re.findall(r"[a-z0-9]+", request.intent.lower()) if len(w) >= 3} - _STOPWORDS
            best_score = 0
            action_id = request.candidates[0].id
            for cand in request.candidates:
                score = len(words & set(re.findall(r"[a-z0-9]+", cand.label.lower())))
                if score > best_score:
                    best_score, action_id = score, cand.id

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
