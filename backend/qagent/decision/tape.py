import json
import hashlib
from typing import Dict, Any, Optional
from qagent.decision.base import Decider
from qagent.domain.schemas import DecisionRequest, DecisionResult


def hash_request(request: DecisionRequest) -> str:
    serialized = json.dumps({
        "step_seq": request.step_seq,
        "intent": request.intent,
        "url": request.url,
        "candidates": [c.model_dump() for c in request.candidates],
    }, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class RecordingDecider:
    """Wraps any Decider and records every request and response onto an in-memory or persisted tape."""

    def __init__(self, inner: Decider):
        self.inner = inner
        self.tape: Dict[str, Dict[str, Any]] = {}

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        req_hash = hash_request(request)
        result = await self.inner.decide(request)
        self.tape[req_hash] = {
            "request": request.model_dump(),
            "response": result.model_dump(),
        }
        return result

    def export_tape(self) -> Dict[str, Dict[str, Any]]:
        return self.tape


class ReplayDecider:
    """Replays decisions deterministically from a recorded tape."""

    def __init__(self, tape: Dict[str, Dict[str, Any]], fallback: Optional[Decider] = None):
        self.tape = tape
        self.fallback = fallback

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        req_hash = hash_request(request)
        if req_hash in self.tape:
            saved = self.tape[req_hash]["response"]
            result = DecisionResult.model_validate(saved)
            result.decider = "replay"
            return result
        
        if self.fallback:
            return await self.fallback.decide(request)
            
        raise KeyError(f"No recorded decision found for request hash {req_hash} in replay tape")
