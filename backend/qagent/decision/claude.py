import asyncio
import base64
import time
from typing import Any, Dict, List, Optional

import httpx

from qagent.config import settings
from qagent.decision.fewshot import example_ids, render_examples
from qagent.domain.schemas import ConfidenceTier, DecisionRequest, DecisionResult

# Sonnet-class list pricing, USD per million tokens.
INPUT_USD_PER_M = 3.0
OUTPUT_USD_PER_M = 15.0

def usage_cost(usage: Dict[str, Any]) -> float:
    """USD for one Bedrock call from its token usage."""
    return usage.get("inputTokens", 0) * INPUT_USD_PER_M / 1e6 + usage.get("outputTokens", 0) * OUTPUT_USD_PER_M / 1e6


CHOOSE_TOOL = {
    "toolSpec": {
        "name": "choose_action",
        "description": "Pick the single page element that best advances the test step.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "candidate_id": {"type": "integer", "description": "id of the chosen candidate"},
                "confidence": {"type": "number", "description": "0.0-1.0 certainty this is the right element"},
                "reasoning": {"type": "string", "description": "one short sentence"},
            },
            "required": ["candidate_id", "confidence", "reasoning"],
        }},
    }
}


class BedrockClient:
    """Minimal Bedrock Converse client (Bearer API key) with forced tool use and 429/5xx retry."""

    def __init__(self, api_key: Optional[str] = None, region: Optional[str] = None, model_id: Optional[str] = None):
        self.api_key = api_key or settings.bedrock_api_key
        self.region = region or settings.bedrock_region
        self.model_id = model_id or settings.bedrock_reasoning_model_id

    @property
    def url(self) -> str:
        return f"https://bedrock-runtime.{self.region}.amazonaws.com/model/{self.model_id}/converse"

    async def converse_tool(self, system: str, user: str, tool: Dict[str, Any], max_tokens: int = 512,
                            images: Optional[List[bytes]] = None, timeout: float = 60.0) -> Dict[str, Any]:
        """Calls the model with `tool` forced; returns {"input": tool_args, "usage": {...}}."""
        if not self.api_key:
            raise RuntimeError("BEDROCK_API_KEY is not set")
        body = {
            "system": [{"text": system}],
            "messages": [{"role": "user", "content": [
                *({"image": {"format": "jpeg", "source": {"bytes": base64.b64encode(img).decode()}}}
                  for img in (images or [])),
                {"text": user},
            ]}],
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.0},
            "toolConfig": {"tools": [tool], "toolChoice": {"tool": {"name": tool["toolSpec"]["name"]}}},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        backoff = 1.0
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(4):
                resp = await client.post(self.url, headers=headers, json=body)
                if resp.status_code in (429, 500, 502, 503, 529) and attempt < 3:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                resp.raise_for_status()
                data = resp.json()
                for block in data["output"]["message"]["content"]:
                    if "toolUse" in block:
                        return {"input": block["toolUse"]["input"], "usage": data.get("usage", {})}
                raise RuntimeError("Bedrock response contained no tool use")
        raise RuntimeError("Bedrock retry loop exhausted")


class ClaudeDecider:
    """Claude on Bedrock as a Decider: used for baseline mode and for escalating low-confidence Jev steps."""

    def __init__(self, client: Optional[BedrockClient] = None, max_candidates: int = 40):
        self.client = client or BedrockClient()
        self.max_candidates = max_candidates

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        candidates = request.candidates[: self.max_candidates]
        listing = "\n".join(f"[{c.id}] <{c.tag}> {c.label!r} (action: {c.action_type})" for c in candidates)
        history = "; ".join(f"{h.get('intent')} -> {h.get('action')}" for h in request.history[-3:]) or "none"
        user = (
            f"Test step: {request.intent}\nPage: {request.url}"
            f"{' (' + request.page_summary + ')' if request.page_summary else ''}\n"
            f"Previous steps: {history}\nCandidates:\n{listing}"
        )
        system = ("You drive a web browser for QA testing. Choose the one candidate that performs the test step. "
                  "Be honest about confidence: lower it when several candidates fit or none does.")
        if request.hints:
            system += "\n\nKnown traps in this app:\n" + "\n".join(f"- {h}" for h in request.hints)
        if request.examples:
            system += "\n\nHow to reason about tricky situations:\n" + render_examples(request.examples)

        started = time.perf_counter()
        out = await self.client.converse_tool(system, user, CHOOSE_TOOL)
        latency_ms = (time.perf_counter() - started) * 1000.0

        args = out["input"]
        valid = {c.id for c in candidates}
        choice = int(args.get("candidate_id", -1))
        confidence = max(0.0, min(1.0, float(args.get("confidence", 0.0))))
        if choice not in valid:  # model hallucinated an id: report it as an unusable decision
            choice, confidence = candidates[0].id if candidates else 0, 0.0

        usage = out["usage"]
        in_tok, out_tok = usage.get("inputTokens", 0), usage.get("outputTokens", 0)
        if confidence >= settings.gate_auto_min:
            tier = ConfidenceTier.AUTO
        elif confidence >= settings.gate_escalate_min:
            tier = ConfidenceTier.ESCALATE
        else:
            tier = ConfidenceTier.STOP
        return DecisionResult(
            decider="claude",
            model_version=self.client.model_id,
            selected_action_id=choice,
            confidence=confidence,
            tier=tier,
            reasoning=args.get("reasoning"),
            probabilities={choice: confidence},
            latency_ms=latency_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=in_tok * INPUT_USD_PER_M / 1e6 + out_tok * OUTPUT_USD_PER_M / 1e6,
            few_shot_ids=example_ids(request.examples),
        )
