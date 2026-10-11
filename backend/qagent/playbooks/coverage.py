from typing import Any, Dict, List


def requirement_coverage(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Which playbook items exercise each requirement.
    A requirement is covered by a flow/edge case that `covers` it, a formula that `verifies` it,
    or by the formulas/rules a covering flow `checks`.
    """
    reqs = [r["key"] for r in parsed.get("requirements", [])]
    covered_by: Dict[str, List[str]] = {r: [] for r in reqs}

    def add(req: str, key: str) -> None:
        if req in covered_by and key not in covered_by[req]:
            covered_by[req].append(key)

    for f in parsed.get("formulas", []):
        for r in f.get("verifies", []):
            add(r, f["key"])
    for fl in parsed.get("flows", []):
        for r in fl.get("covers", []):
            add(r, fl["key"])
    for ec in parsed.get("edge_cases", []):
        for r in ec.get("covers", []):
            add(r, ec["key"])
    for ux in parsed.get("ux_rules", []):
        for r in ux.get("covers", []):
            add(r, ux["key"])

    return {
        "covered_by": covered_by,
        "uncovered": [r for r, keys in covered_by.items() if not keys],
    }
