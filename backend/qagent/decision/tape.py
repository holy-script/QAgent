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
    """
    Replays decisions deterministically from a recorded tape, matched by input hash. If the hash is not on the
    tape but a decision was recorded for the same step and intent, the page differs from the recording: that
    decision is replayed anyway and a divergence is noted for the engine to report.
    """

    def __init__(self, tape: Dict[str, Dict[str, Any]], fallback: Optional[Decider] = None):
        self.tape = tape
        self.fallback = fallback
        self._by_step = {(e["step_seq"], e["intent"]): (h, e) for h, e in tape.items()
                         if e.get("step_seq") is not None}
        self._divergences: Dict[str, Dict[str, Any]] = {}

    def take_divergence(self, input_hash: str) -> Optional[Dict[str, Any]]:
        return self._divergences.pop(input_hash, None)

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        req_hash = hash_request(request)
        if req_hash in self.tape:
            return self._replayed(self.tape[req_hash])

        recorded = self._by_step.get((request.step_seq, request.intent))
        if recorded is not None:
            expected_hash, entry = recorded
            self._divergences[req_hash] = {"step_seq": request.step_seq, "expected_hash": expected_hash,
                                           "actual_hash": req_hash}
            return self._replayed(entry)

        if self.fallback:
            return await self.fallback.decide(request)
        raise KeyError(f"No recorded decision found for request hash {req_hash} in replay tape")

    @staticmethod
    def _replayed(entry: Dict[str, Any]) -> DecisionResult:
        result = DecisionResult.model_validate(entry["response"])
        result.decider = "replay"
        return result
