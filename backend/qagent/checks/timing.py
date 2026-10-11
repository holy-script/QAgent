import re
from typing import Any, Dict, Optional

from qagent.checks.base import CheckOutcome

_ID = re.compile(r"/(?:\d+|[0-9a-f]{8}-[0-9a-f-]{27,})(?=/|$)", re.IGNORECASE)


def normalize_endpoint(method: str, url: str) -> str:
    """'POST http://h/api/items/42?x=1' -> 'POST /api/items/:id' (stable across runs, used for fingerprints)."""
    from urllib.parse import urlparse
    path = _ID.sub("/:id", urlparse(url).path)
    return f"{method} {path}"


def network_check(call: Dict[str, Any], flow_expects_error: bool = False) -> CheckOutcome:
    endpoint = normalize_endpoint(call["method"], call["url"])
    status = call["status"]
    bad = status >= 500 or (400 <= status < 500 and not flow_expects_error)
    return CheckOutcome(
        key=f"network:{endpoint}", kind="network", passed=not bad, severity="high", finding_kind="network",
        title=f"{'Server' if status >= 500 else 'Client'} error on {endpoint}",
        expected="HTTP status below 400" if not flow_expects_error else "HTTP status below 500",
        actual=f"HTTP {status}", inputs={"url": call["url"], "status": status, "duration_ms": call["duration_ms"]},
        locus=endpoint, evidence={"status": status, "url": call["url"], "method": call["method"]},
    )


def slow_call_check(call: Dict[str, Any], sla_ms: float) -> Optional[CheckOutcome]:
    if call["duration_ms"] <= sla_ms:
        return None
    endpoint = normalize_endpoint(call["method"], call["url"])
    return CheckOutcome(
        key=f"timing:{endpoint}", kind="timing", passed=False, severity="medium", finding_kind="timing",
        title=f"Slow API call: {endpoint}", expected=f"response within {sla_ms:.0f}ms",
        actual=f"{call['duration_ms']:.0f}ms", inputs={"url": call["url"]}, locus=endpoint,
        evidence={"duration_ms": call["duration_ms"], "sla_ms": sla_ms},
    )


def step_timing_check(duration_ms: float, sla_ms: float, step_seq: int, flow_key: str) -> CheckOutcome:
    return CheckOutcome(
        key=f"timing:step:{flow_key}", kind="timing", passed=duration_ms <= sla_ms, severity="medium",
        finding_kind="timing", title=f"Step {step_seq} exceeded {sla_ms:.0f}ms",
        expected=f"step completes within {sla_ms:.0f}ms", actual=f"{duration_ms:.0f}ms",
        inputs={"duration_ms": duration_ms}, locus=f"step:{step_seq}",
        evidence={"duration_ms": duration_ms, "sla_ms": sla_ms},
    )


def settle_check(settled: bool, waited_ms: float, step_seq: int, flow_key: str) -> CheckOutcome:
    return CheckOutcome(
        key=f"timing:settle:{flow_key}", kind="timing", passed=settled, severity="high", finding_kind="timing",
        title="Page never settled: loading indicator still visible",
        expected="Loading indicator clears after the action",
        actual="settled" if settled else f"Still busy after {waited_ms:.0f}ms",
        inputs={"waited_ms": waited_ms, "step_seq": step_seq}, locus="loading-indicator",
        evidence={"waited_ms": waited_ms},
    )
