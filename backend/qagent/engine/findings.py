from typing import Dict, Any, List, Optional
from qagent.domain.schemas import Finding, FindingSeverity, FindingKind
from qagent.playbooks.formulas import evaluate_formula


class Verifier:
    """Evaluates DOM assertions, status codes, timing SLAs (>2s), and formulas."""

    @staticmethod
    def check_timing(duration_ms: float, sla_ms: float = 2000.0, step_seq: int = 1, flow_run_id: str = "") -> Optional[Finding]:
        if duration_ms > sla_ms:
            return Finding(
                id=f"find-timing-{step_seq}",
                flow_run_id=flow_run_id,
                step_seq=step_seq,
                severity=FindingSeverity.MEDIUM,
                kind=FindingKind.TIMING,
                title=f"Step execution exceeded SLA threshold ({duration_ms:.1f}ms > {sla_ms:.0f}ms)",
                expected=f"Latency <= {sla_ms}ms",
                actual=f"{duration_ms:.1f}ms",
                evidence={"duration_ms": duration_ms, "sla_ms": sla_ms},
            )
        return None

    @staticmethod
    def check_network_status(status: int, url: str, step_seq: int = 1, flow_run_id: str = "") -> Optional[Finding]:
        if status >= 500:
            return Finding(
                id=f"find-net-{step_seq}",
                flow_run_id=flow_run_id,
                step_seq=step_seq,
                severity=FindingSeverity.HIGH,
                kind=FindingKind.NETWORK,
                title=f"Internal Server Error on {url}",
                expected="HTTP 200/201/204",
                actual=f"HTTP {status}",
                evidence={"status": status, "url": url},
            )
        return None

    @staticmethod
    def check_formula(
        formula_name: str,
        expression: str,
        context: Dict[str, Any],
        step_seq: int = 1,
        flow_run_id: str = "",
    ) -> Optional[Finding]:
        passed = evaluate_formula(expression, context)
        if not passed:
            return Finding(
                id=f"find-formula-{step_seq}",
                flow_run_id=flow_run_id,
                step_seq=step_seq,
                severity=FindingSeverity.HIGH,
                kind=FindingKind.FORMULA,
                title=f"Formula verification failed: {formula_name}",
                expected=expression,
                actual=f"Context evaluated to false: {context}",
                evidence={"context": context, "formula": expression},
            )
        return None
