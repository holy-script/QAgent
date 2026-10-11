from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from qagent.config import settings
from qagent.decision.claude import BedrockClient
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
        return Verdict(p >= 0.5, p, "jev", abs(p - 0.5) * 2)

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
        return Verdict(yes, conf if yes else 1 - conf, "claude", conf, a.get("reasoning", ""),
                       few_shot_ids=example_ids(examples))

    async def ask(self, question: str, page_text: str, screenshots: Optional[List[bytes]] = None,
                  hints: Optional[List[str]] = None, examples: Optional[List[Dict[str, Any]]] = None) -> Verdict:
        hints, examples, screenshots = hints or [], examples or [], screenshots or []
        first: Optional[Verdict] = None
        if self.jev:
            first = await self._jev(question, page_text, hints)
            if first.confidence >= settings.gate_auto_min or not self.claude:
                return first
        return await self._claude(question, page_text, hints, examples, screenshots)
