import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from qagent.config import settings
from qagent.decision.claude import BedrockClient, usage_cost
from qagent.decision.fewshot import example_ids, render_examples
from qagent.decision.jev import JevDecider

YES_NO_TOOL = {
    "toolSpec": {
        "name": "answer_yes_no",
        "description": "Answer the yes/no question about the page.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "answer": {"type": "boolean"},
                "confidence": {"type": "number", "description": "0.0-1.0"},
                "reasoning": {"type": "string", "description": "one short sentence citing what you saw"},
            },
            "required": ["answer", "confidence", "reasoning"],
        }},
    }
}


@dataclass
class Verdict:
    passed: bool            # the statement is true
    probability: float      # P(true)
    judged_by: str          # jev | claude
    confidence: float
    reasoning: str = ""
    few_shot_ids: Optional[List[str]] = None
    model_version: str = ""
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Verdict":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class Judge:
    """
    Answers yes/no questions about a page. Jev answers first as a `noul` question over the page text
    (confidence is abs(p - 0.5) * 2, since noul answers carry none). If that is below the auto
    threshold and Claude is configured, Claude answers from the page text plus screenshots.
    """

    def __init__(self, jev: Optional[JevDecider] = None, claude: Optional[BedrockClient] = None):
        self.jev = jev
        self.claude = claude

    @classmethod
    def from_settings(cls, use_jev: bool = True, use_claude: bool = True) -> Optional["Judge"]:
        jev = JevDecider() if use_jev and settings.active_jev_token else None
        claude = BedrockClient() if use_claude and settings.bedrock_api_key else None
        return cls(jev, claude) if (jev or claude) else None

    async def _jev(self, question: str, page_text: str, hints: List[str]) -> Verdict:
        assert self.jev
        payload = {
            "model": self.jev.model,
            "state": {"page_text": page_text[:4000], "known_traps": hints[:2]},
            "questions": {"answer": {"type": "noul", "instructions": question}},
        }
        data = await self.jev._post_with_retry(
            url=f"{self.jev.base_url}/v1/systemone",
            headers={"Authorization": f"Bearer {self.jev.api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        p = float(data["answers"]["answer"]["noul"])
        usage = data.get("usage", {})
        return Verdict(p >= 0.5, p, "jev", abs(p - 0.5) * 2, model_version=self.jev.model,
                       input_tokens=usage.get("input_tokens", 0), output_tokens=usage.get("output_tokens", 0))

    async def _claude(self, question: str, page_text: str, hints: List[str], examples: List[Dict[str, Any]],
                      screenshots: List[bytes]) -> Verdict:
        assert self.claude
        system = ("You judge whether a statement about a web page is true, using the page text and screenshots. "
                  "Answer strictly from what is visible; lower your confidence when the evidence is thin.")
        if hints:
            system += "\n\nKnown traps in this app:\n" + "\n".join(f"- {h}" for h in hints)
        if examples:
            system += "\n\nHow to reason about tricky situations:\n" + render_examples(examples)
        out = await self.claude.converse_tool(
            system, f"Question: {question}\n\nPage text:\n{page_text[:4000]}", YES_NO_TOOL, images=screenshots[:2])
        a = out["input"]
        yes = bool(a["answer"])
        conf = max(0.0, min(1.0, float(a.get("confidence", 0.5))))
        usage = out.get("usage", {})
        return Verdict(yes, conf if yes else 1 - conf, "claude", conf, a.get("reasoning", ""),
                       few_shot_ids=example_ids(examples), model_version=self.claude.model_id,
                       input_tokens=usage.get("inputTokens", 0), output_tokens=usage.get("outputTokens", 0),
                       cost_usd=usage_cost(usage))

    async def ask(self, question: str, page_text: str, screenshots: Optional[List[bytes]] = None,
                  hints: Optional[List[str]] = None, examples: Optional[List[Dict[str, Any]]] = None) -> Verdict:
        hints, examples, screenshots = hints or [], examples or [], screenshots or []
        started = time.perf_counter()
        first: Optional[Verdict] = None
        if self.jev:
            first = await self._jev(question, page_text, hints)
            if first.confidence >= settings.gate_auto_min or not self.claude:
                first.latency_ms = (time.perf_counter() - started) * 1000.0
                return first
        verdict = await self._claude(question, page_text, hints, examples, screenshots)
        if first:  # the escalation paid for both answers
            verdict.input_tokens += first.input_tokens
            verdict.output_tokens += first.output_tokens
        verdict.latency_ms = (time.perf_counter() - started) * 1000.0
        return verdict

    @property
    def can_verify(self) -> bool:
        return self.claude is not None

    async def verify(self, question: str, page_text: str, page: Any, journey: str = "", hints: Optional[List[str]] = None,
                     examples: Optional[List[Dict[str, Any]]] = None, console_logs: Optional[List[Dict[str, Any]]] = None,
                     state_js: Optional[str] = None, network_calls: Optional[List[Dict[str, Any]]] = None) -> Optional[Verdict]:
        """Works on the live page (clicks, hovers) to answer; None when there is no strong model or the evidence stays inconclusive."""
        if not self.claude:
            return None
        from qagent.checks.verifier import verify_live
        return await verify_live(self.claude, page, question, journey, hints, examples, console_logs, state_js,
                                 network_calls=network_calls)
