from typing import Any, Dict, List, Optional

from qagent.domain.runspec import FlowSpec


def flow_from_parsed(f: Dict[str, Any]) -> FlowSpec:
    return FlowSpec(
        key=f["key"], severity=f.get("severity", "high"), steps=list(f.get("steps", [])),
        expect=list(f.get("expect", [])), test_data=dict(f.get("test_data", {})),
        covers=list(f.get("covers", [])), checks=list(f.get("checks", [])),
    )


def expand_flows(parsed: Dict[str, Any], flow_keys: Optional[List[str]] = None,
                 include_edge_cases: bool = True) -> List[FlowSpec]:
    """
    Base flows plus one variant per edge case that applies to them. `EC-3` on `checkout` runs as
    `checkout#EC-3`: same steps, test data overridden by the edge case, and its `expect` replaces the
    flow's expectations (the base expectations describe the happy path).
    """
    flows: List[FlowSpec] = []
    for f in parsed["flows"]:
        if flow_keys and f["key"] not in flow_keys:
            continue
        base = flow_from_parsed(f)
        flows.append(base)
        if not include_edge_cases:
            continue
        for ec in parsed.get("edge_cases", []):
            if ec.get("applies_to") != f["key"]:
                continue
            flows.append(base.model_copy(update={
                "key": f"{f['key']}#{ec['key']}",
                "variant_of": f["key"],
                "edge_case": ec["key"],
                "test_data": {**base.test_data, **ec.get("test_data", {})},
                "expect": [ec["expect"]] if ec.get("expect") else [],
                "covers": sorted(set(base.covers) | set(ec.get("covers", []))),
                "checks": list(dict.fromkeys(base.checks + ec.get("checks", []))),
            }))
    return flows


def spec_items(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Playbook items the engine needs at run time, keyed by ID."""
    return {
        "requirements": {r["key"]: r for r in parsed.get("requirements", [])},
        "formulas": {f["key"]: f for f in parsed.get("formulas", [])},
        "ux_rules": {u["key"]: u for u in parsed.get("ux_rules", [])},
        "gotchas": parsed.get("gotchas", []),
        "reasoning_examples": parsed.get("reasoning_examples", []),
        "playbook_hash": parsed.get("content_hash", ""),
    }
