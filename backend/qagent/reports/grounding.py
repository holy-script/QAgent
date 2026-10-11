from typing import Any, Dict, Iterable, List, Tuple

CATEGORIES = {"functional", "ux", "performance", "accessibility", "test_coverage"}
CONFIDENCE = {"high", "medium", "low"}
EFFORT = {"s", "m", "l"}


def ground_recommendations(raw: Iterable[Dict[str, Any]], finding_ids: Iterable[str],
                           requirement_keys: Iterable[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Keeps only recommendations that point at real facts. Returns (kept, dropped-with-reason).
    A recommendation must cite at least one existing finding (a test-coverage recommendation may cite an
    existing requirement instead); every ID it cites must exist; enum fields must be valid.
    """
    findings, reqs = set(finding_ids), set(requirement_keys)
    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    for rec in raw:
        cited_f = list(rec.get("evidence_finding_ids") or [])
        cited_r = list(rec.get("requirement_keys") or [])
        reason = None
        if not rec.get("text") or not rec.get("rationale"):
            reason = "missing text or rationale"
        elif rec.get("category") not in CATEGORIES:
            reason = f"unknown category {rec.get('category')!r}"
        elif any(f not in findings for f in cited_f):
            reason = "cites a finding that does not exist"
        elif any(r not in reqs for r in cited_r):
            reason = "cites a requirement that does not exist"
        elif not cited_f and not (rec.get("category") == "test_coverage" and cited_r):
            reason = "cites no finding"
        elif rec.get("confidence") not in CONFIDENCE or rec.get("effort") not in EFFORT:
            reason = "invalid confidence or effort"
        if reason:
            dropped.append({**rec, "dropped_because": reason})
        else:
            kept.append(rec)
    return kept, dropped
