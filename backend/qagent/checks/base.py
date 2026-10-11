from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]


def max_severity(*values: str) -> str:
    return max((v for v in values if v in SEVERITY_ORDER), key=SEVERITY_ORDER.index, default="medium")


@dataclass
class CheckOutcome:
    """Result of one check. Failed outcomes become findings; every outcome is stored as a check_results row."""
    key: str                                  # F-1, UX-2, expect:add-to-cart:1, network:POST /api/pay
    kind: str                                 # formula, ux_rule, ux_judged, expectation, network, timing
    passed: bool
    title: str
    expected: str = ""
    actual: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)   # bound values and where each came from
    judged_by: str = "code"                   # code | jev | claude
    confidence: Optional[float] = None
    severity: str = "high"
    requirement_keys: List[str] = field(default_factory=list)
    locus: str = ""                           # endpoint path or selector, used for issue fingerprints
    finding_kind: Optional[str] = None        # overrides kind when mapping to a finding (formula | dom | network | timing)
    evidence: Dict[str, Any] = field(default_factory=dict)
