import uuid
from typing import Any, Dict, Optional

from qagent.domain.schemas import Finding, FindingKind, FindingSeverity
from qagent.playbooks.formulas import evaluate_formula_strict


def _fid() -> str:
    return f"find-{uuid.uuid4().hex[:12]}"


class Verifier:
    """Pure checks: timing SLA, network status, formulas, settle timeouts. No I/O."""

    @staticmethod
    def check_timing(duration_ms: float, sla_ms: float = 2000.0, step_seq: int = 1, flow_run_id: str = "") -> Optional[Finding]:
        if duration_ms <= sla_ms:
            return None
        return Finding(
            id=_fid(),
            flow_run_id=flow_run_id,
            step_seq=step_seq,
            severity=FindingSeverity.MEDIUM,
            kind=FindingKind.TIMING,
            title=f"Step exceeded {sla_ms:.0f}ms SLA ({duration_ms:.0f}ms)",
            expected=f"Step completes within {sla_ms:.0f}ms",
            actual=f"{duration_ms:.0f}ms",
            evidence={"duration_ms": duration_ms, "sla_ms": sla_ms},
        )

    @staticmethod
    def check_unsettled(waited_ms: float, step_seq: int = 1, flow_run_id: str = "") -> Finding:
        return Finding(
            id=_fid(),
            flow_run_id=flow_run_id,
            step_seq=step_seq,
            severity=FindingSeverity.HIGH,
            kind=FindingKind.TIMING,
            title="Page never settled: loading indicator still visible",
            expected="Loading indicator clears after the action",
            actual=f"Still busy after {waited_ms:.0f}ms",
            evidence={"waited_ms": waited_ms},
        )

    @staticmethod
    def check_network_status(status: int, url: str, step_seq: int = 1, flow_run_id: str = "", method: str = "GET") -> Optional[Finding]:
        if status < 500:
            return None
        return Finding(
            id=_fid(),
            flow_run_id=flow_run_id,
            step_seq=step_seq,
            severity=FindingSeverity.HIGH,
            kind=FindingKind.NETWORK,
            title=f"Server error on {method} {url}",
            expected="HTTP status below 500",
            actual=f"HTTP {status}",
            evidence={"status": status, "url": url, "method": method},
        )

    @staticmethod
    def check_formula(
        formula_name: str,
        expression: str,
        context: Dict[str, Any],
        step_seq: int = 1,
        flow_run_id: str = "",
        kind: str = "formula",
        severity: FindingSeverity = FindingSeverity.HIGH,
    ) -> Optional[Finding]:
        finding_kind = FindingKind.DOM if kind == "dom" else FindingKind.FORMULA
        try:
            if evaluate_formula_strict(expression, context):
                return None
            title = f"Check failed: {formula_name}"
            actual = f"Evaluated to false with {context}"
        except Exception as exc:
            title = f"Check could not be evaluated: {formula_name}"
            actual = f"{type(exc).__name__}: {exc}"
        return Finding(
            id=_fid(),
            flow_run_id=flow_run_id,
            step_seq=step_seq,
            severity=severity,
            kind=finding_kind,
            title=title,
            expected=expression,
            actual=actual,
            evidence={"context": context, "formula": expression, "name": formula_name},
        )
