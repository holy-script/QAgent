"""
The run's tape beyond step decisions: judge verdicts and report calls.

`TapedJudge` wraps a Judge. Live, it records each verdict as a `model.call` event (with tokens, latency and cost).
On replay it serves the recorded verdict for the same question and page text, so a repeated run needs no model calls.
`LedgerClient` does the same for Claude report calls (impact, recommendations).
"""
import contextvars
import hashlib
import json
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from qagent.checks.ux_judged import Judge, Verdict
from qagent.decision.claude import BedrockClient, usage_cost

current_flow_run: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_flow_run", default=None)
Emit = Callable[[Dict[str, Any]], Awaitable[None]]


def call_hash(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def judge_hash(question: str, page_text: str, hints: List[str]) -> str:
    return call_hash("judge", question, page_text[:4000], hints[:2])


class TapedJudge:
    def __init__(self, inner: Optional[Judge] = None, tape: Optional[Dict[str, Dict[str, Any]]] = None):
        """`tape` (hash -> recorded verdict) makes this a replay; `inner` answers what the tape lacks (or everything, live)."""
        self.inner = inner
        self.tape = tape
        self._emit: Optional[Emit] = None
        self.divergent = 0

    def bind(self, emit: Emit) -> None:
        self._emit = emit

    async def ask(self, question: str, page_text: str, screenshots: Optional[List[bytes]] = None,
                  hints: Optional[List[str]] = None, examples: Optional[List[Dict[str, Any]]] = None) -> Verdict:
        key = judge_hash(question, page_text, hints or [])
        recorded = self.tape.get(key) if self.tape is not None else None
        if recorded is not None:
            verdict, replayed = Verdict.from_dict(recorded), True
        elif self.inner is not None:
            verdict, replayed = await self.inner.ask(question, page_text, screenshots, hints, examples), False
            if self.tape is not None:
                self.divergent += 1  # live call during a replay: the page differs from the recording
        else:
            raise LookupError("this judgement is not on the tape")
        if self._emit:
            await self._emit({
                "flow_run_id": current_flow_run.get(), "purpose": "judge", "decider": verdict.judged_by,
                "model_version": verdict.model_version, "label": question[:300], "input_hash": key,
                "response": verdict.to_dict(), "latency_ms": 0.0 if replayed else verdict.latency_ms,
                "input_tokens": 0 if replayed else verdict.input_tokens,
                "output_tokens": 0 if replayed else verdict.output_tokens,
                "cost_usd": 0.0 if replayed else verdict.cost_usd, "replayed": replayed,
            })
        return verdict

    @property
    def can_verify(self) -> bool:
        return self.tape is not None or bool(getattr(self.inner, "can_verify", False))

    async def verify(self, question: str, page_text: str, page: Any, journey: str = "", hints: Optional[List[str]] = None,
                     examples: Optional[List[Dict[str, Any]]] = None, console_logs: Optional[List[Dict[str, Any]]] = None,
                     state_js: Optional[str] = None) -> Optional[Verdict]:
        """Live verification (see checks/verifier.py), on the tape like any judgement: a repeat serves the recorded verdict."""
        key = judge_hash("verify: " + question, page_text, hints or [])
        recorded = self.tape.get(key) if self.tape is not None else None
        if recorded is not None:
            verdict, replayed = (Verdict.from_dict(recorded) if recorded.get("inconclusive") is not True else None), True
        elif getattr(self.inner, "can_verify", False):
            verdict, replayed = await self.inner.verify(question, page_text, page, journey, hints, examples, console_logs, state_js), False
            if self.tape is not None:
                self.divergent += 1
        else:
            raise LookupError("this live check is not on the tape")
        if self._emit:
            body = verdict.to_dict() if verdict else {"inconclusive": True}
            await self._emit({
                "flow_run_id": current_flow_run.get(), "purpose": "judge", "decider": "claude",
                "model_version": verdict.model_version if verdict else "", "label": ("verify: " + question)[:300],
                "input_hash": key, "response": body,
                "latency_ms": 0.0 if replayed or not verdict else verdict.latency_ms,
                "input_tokens": 0 if replayed or not verdict else verdict.input_tokens,
                "output_tokens": 0 if replayed or not verdict else verdict.output_tokens,
                "cost_usd": 0.0 if replayed or not verdict else verdict.cost_usd, "replayed": replayed,
            })
        return verdict


PURPOSE = {"bug_narrative": "bug_narrative", "plan_flow": "planner", "next_step": "director"}  # any other tool is a report call


class LedgerClient:
    """BedrockClient look-alike that records every call as a ModelCall row and, on replay, serves recorded answers."""

    def __init__(self, inner: BedrockClient, record: Callable[[Dict[str, Any]], Awaitable[None]],
                 tape: Optional[Dict[str, Dict[str, Any]]] = None, strict: bool = False):
        """`strict`: with a tape, a call that is not on it is an error instead of a live call (a repeat must not spend money)."""
        self.inner, self.record, self.tape, self.strict = inner, record, tape, strict

    @property
    def model_id(self) -> str:
        return self.inner.model_id

    async def converse_tool(self, system: str, user: str, tool: Dict[str, Any], max_tokens: int = 512,
                            images: Optional[List[bytes]] = None) -> Dict[str, Any]:
        name = tool["toolSpec"]["name"]
        key = call_hash(name, system, user)
        hit = self.tape.get(key) if self.tape is not None else None
        if hit is not None:
            await self.record({"purpose": PURPOSE.get(name, "report"), "decider": "claude",
                               "model_version": self.model_id, "label": name, "input_hash": key,
                               "response": hit, "replayed": True, "flow_run_id": current_flow_run.get()})
            return {"input": hit, "usage": {}}
        if self.strict and self.tape is not None:
            raise LookupError("this model call is not on the tape")
        started = time.perf_counter()
        out = await self.inner.converse_tool(system, user, tool, max_tokens, images)
        usage = out.get("usage", {})
        await self.record({"purpose": PURPOSE.get(name, "report"), "decider": "claude",
                           "model_version": self.model_id, "label": name, "input_hash": key, "response": out["input"],
                           "flow_run_id": current_flow_run.get(),
                           "latency_ms": (time.perf_counter() - started) * 1000.0,
                           "input_tokens": usage.get("inputTokens", 0), "output_tokens": usage.get("outputTokens", 0),
                           "cost_usd": usage_cost(usage), "replayed": False})
        return out
