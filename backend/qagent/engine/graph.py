import asyncio
import time
from typing import Dict, Any, Optional
from qagent.domain.runspec import RunSpec, FlowSpec
from qagent.domain.schemas import CandidateAction, DecisionRequest, DecisionResult, ConfidenceTier
from qagent.domain.events import QAgentEventType
from qagent.decision.base import Decider
from qagent.decision.stub import StubDecider
from qagent.decision.jev import JevDecider
from qagent.storage.persistence_sink import PersistenceSink
from qagent.storage.upload_queue import upload_queue
from qagent.engine.findings import Verifier
from qagent.engine.gating import evaluate_gate
from qagent.engine.tracing import logger


class EngineRunner:
    """
    Core engine runner implementing the loop:
    observe -> decide -> gate -> act -> verify -> next_step
    Emits events strictly to PersistenceSink and uploads artifacts to UploadQueue.
    """

    def __init__(self, run_spec: RunSpec, decider: Decider, sink: PersistenceSink):
        self.spec = run_spec
        self.decider = decider
        self.sink = sink
        self.findings_count = 0

    async def run(self) -> Dict[str, Any]:
        logger.info("engine.run.started", run_id=self.spec.run_id, mode=self.spec.mode)
        
        await self.sink.emit(
            QAgentEventType.RUN_STARTED,
            {
                "run_id": self.spec.run_id,
                "target_url": self.spec.base_url,
                "mode": self.spec.mode.value,
                "flow_count": len(self.spec.flows),
            }
        )

        total_steps = 0
        start_time = time.perf_counter()

        for flow in self.spec.flows:
            flow_steps = await self._run_flow(flow)
            total_steps += flow_steps

        duration_s = time.perf_counter() - start_time

        await self.sink.emit(
            QAgentEventType.RUN_FINISHED,
            {
                "run_id": self.spec.run_id,
                "outcome": "PASSED" if self.findings_count == 0 else "FAILED",
                "total_steps": total_steps,
                "duration_s": duration_s,
                "findings_count": self.findings_count,
            }
        )

        return {
            "run_id": self.spec.run_id,
            "status": "passed" if self.findings_count == 0 else "failed",
            "total_steps": total_steps,
            "duration_s": duration_s,
            "findings_count": self.findings_count,
        }

    async def _run_flow(self, flow: FlowSpec) -> int:
        await self.sink.emit(
            QAgentEventType.FLOW_STARTED,
            {
                "flow_key": flow.key,
                "severity": flow.severity,
                "total_steps": len(flow.steps),
            }
        )

        flow_steps = 0
        for idx, step_intent in enumerate(flow.steps, start=1):
            flow_steps += 1
            step_seq = idx

            # 1. Observe (simulated or browser)
            candidates = [
                CandidateAction(id=1, tag="a", selector="nav a", label="Catalog"),
                CandidateAction(id=2, tag="button", selector="button.primary", label=step_intent),
            ]
            await self.sink.emit(
                QAgentEventType.STEP_OBSERVED,
                {
                    "step_seq": step_seq,
                    "url": f"{self.spec.base_url}/{step_intent.replace(' ', '-').lower()}",
                    "intent": step_intent,
                    "candidates_count": len(candidates),
                }
            )

            # 2. Decide
            req = DecisionRequest(
                step_seq=step_seq,
                intent=step_intent,
                url=self.spec.base_url,
                candidates=candidates,
            )
            decision = await self.decider.decide(req)

            await self.sink.emit(
                QAgentEventType.DECISION_MADE,
                {
                    "step_seq": step_seq,
                    "decider": decision.decider,
                    "selected_action_id": decision.selected_action_id,
                    "confidence": decision.confidence,
                    "tier": decision.tier.value,
                    "latency_ms": decision.latency_ms,
                }
            )

            # 3. Gate
            gate_tier = evaluate_gate(
                decision.confidence,
                self.spec.gate_auto_min,
                self.spec.gate_escalate_min,
            )
            await self.sink.emit(
                QAgentEventType.GATE_TRIGGERED,
                {
                    "step_seq": step_seq,
                    "tier": gate_tier.value,
                    "reason": f"Confidence {decision.confidence:.2f}",
                }
            )

            # 4. Act
            await self.sink.emit(
                QAgentEventType.ACTION_EXECUTED,
                {
                    "step_seq": step_seq,
                    "action_id": decision.selected_action_id,
                    "status": "success",
                    "duration_ms": 120.0,
                }
            )

            # Enqueue step screenshot artifact
            await upload_queue.enqueue(
                key=f"apps/{self.spec.app_id}/runs/{self.spec.run_id}/steps/{step_seq}/screenshot.jpg",
                data=b"\xff\xd8\xff\xe0mock_step_screenshot",
                content_type="image/jpeg",
                run_id=self.spec.run_id,
                step_seq=step_seq,
                kind="screenshot",
            )

            # 5. Verify formulas or timing
            if flow.formulas and "cart_total" in flow.formulas:
                finding = Verifier.check_formula(
                    "cart_total",
                    flow.formulas["cart_total"],
                    {"total": 100.0, "items": [], "tax_rate": 0.08},
                    step_seq=step_seq,
                )
                if finding:
                    self.findings_count += 1
                    await self.sink.emit(
                        QAgentEventType.FINDING_DISCOVERED,
                        finding.model_dump(),
                    )

        await self.sink.emit(
            QAgentEventType.FLOW_FINISHED,
            {
                "flow_key": flow.key,
                "status": "completed",
                "step_count": flow_steps,
            }
        )

        return flow_steps
