import hashlib
from typing import Iterable, List

from qagent.checks.base import SEVERITY_ORDER, max_severity


def fingerprint(check_key: str, flow_key: str, kind: str, locus: str) -> str:
    """
    Stable identity of a bug across runs: the check, the flow (without its edge-case variant suffix),
    the finding kind and a normalized locus (endpoint path with IDs stripped, or the UI selector).
    """
    base_flow = flow_key.split("#", 1)[0]
    raw = "|".join([check_key, base_flow, kind, locus])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def final_severity(base: str, requirement_priorities: Iterable[str], judged: bool) -> str:
    """Raised to the highest violated requirement priority; judged findings never exceed medium."""
    severity = max_severity(base, *requirement_priorities)
    if judged and SEVERITY_ORDER.index(severity) > SEVERITY_ORDER.index("medium"):
        return "medium"
    return severity
