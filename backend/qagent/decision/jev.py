import asyncio
import time
from typing import Dict, Any, Optional
import httpx
from qagent.config import settings
from qagent.decision.base import Decider
from qagent.domain.schemas import DecisionRequest, DecisionResult, ConfidenceTier


class JevDecider:
    """
    Decider integrating with TypeSafe AI (Jev API).
    Includes:
    - Semaphore concurrency limiter (JEV_MAX_CONCURRENCY=4)
    - Exponential backoff retry on 429 / 529 HTTP status codes
    - Model version capture
    - Latency and token tracking
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_concurrency: Optional[int] = None,
    ):
        self.api_key = api_key or settings.active_jev_token
        self.base_url = (base_url or settings.typesafe_base_url).rstrip("/")
        self.model = model or settings.jev_model
        concurrency = max_concurrency or settings.jev_max_concurrency
        self.semaphore = asyncio.Semaphore(concurrency)

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        if not self.api_key:
            # Fallback if no API key present in test environments
            return self._fallback_decision(request)

        # TypeSafe System One API: `state` is the content, `questions` are named; a "choice"
        # question returns the chosen criteria key, a confidence and per-choice probabilities.
        payload = {
            "model": self.model,
            "state": {
                "test_step": request.intent,
                "page_url": request.url,
                "page_summary": request.page_summary or "",
                "previous_steps": [
                    f"{h.get('intent')} -> {h.get('action')}" for h in request.history[-3:]
                ],
            },
            "questions": {
                "action": {
                    "type": "choice",
                    "instructions": "Which page element performs the test step?",
                    "criteria": {
                        str(c.id): f"<{c.tag}> {c.label} (action: {c.action_type})"
                        for c in request.candidates
                    },
                }
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        start_time = time.perf_counter()

        async with self.semaphore:
            response_data = await self._post_with_retry(
                url=f"{self.base_url}/v1/systemone",
                headers=headers,
                json=payload,
            )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        answer = response_data["answers"]["action"]
        valid = {c.id for c in request.candidates}
        choice = int(answer["choice"])
        confidence = float(answer.get("confidence", 0.0))
        if choice not in valid:
            choice, confidence = (request.candidates[0].id if request.candidates else 0), 0.0
        probs = {int(k): float(v) for k, v in answer.get("probabilities", {}).items() if int(k) in valid}
        usage = response_data.get("usage", {})

        tier = ConfidenceTier.AUTO
        if confidence < settings.gate_escalate_min:
            tier = ConfidenceTier.STOP
        elif confidence < settings.gate_auto_min:
            tier = ConfidenceTier.ESCALATE

        return DecisionResult(
            decider="jev",
            model_version=response_data.get("model", self.model),
            selected_action_id=choice,
            confidence=confidence,
            tier=tier,
            reasoning=None,
            probabilities=probs or {choice: confidence},
            latency_ms=latency_ms,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cost_usd=0.0,  # TypeSafe does not publish per-token pricing; output tokens are free
        )

    async def _post_with_retry(self, url: str, headers: Dict[str, str], json: Dict[str, Any]) -> Dict[str, Any]:
        max_retries = 3
        backoff = 0.5

        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(max_retries):
                try:
                    resp = await client.post(url, headers=headers, json=json)
                    if resp.status_code in (429, 529):
                        if attempt == max_retries - 1:
                            resp.raise_for_status()
                        await asyncio.sleep(backoff)
                        backoff *= 2.0
                        continue

                    resp.raise_for_status()
                    return resp.json()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (429, 529) and attempt < max_retries - 1:
                        await asyncio.sleep(backoff)
                        backoff *= 2.0
                        continue
                    raise

        raise RuntimeError("Jev API retry loop exhausted")

    def _fallback_decision(self, request: DecisionRequest) -> DecisionResult:
        choice = request.candidates[0].id if request.candidates else 1
        return DecisionResult(
            decider="jev",
            model_version=self.model,
            selected_action_id=choice,
            confidence=0.92,
            tier=ConfidenceTier.AUTO,
            reasoning="Jev mock response (no API token supplied)",
            probabilities={choice: 0.92},
            latency_ms=25.0,
            input_tokens=50,
            output_tokens=10,
            cost_usd=0.0004,
        )
