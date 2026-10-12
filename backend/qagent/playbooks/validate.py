import ast
import re
from typing import Any, Dict, List, Optional, Set

from qagent.playbooks.coverage import requirement_coverage
from qagent.playbooks.schema import (
    FORMULA_FUNCTIONS, KNOWN_FIELDS, PRIORITIES, RX_SCOPES, SEVERITIES, UX_CHECK_TYPES,
)

_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Call, ast.Constant, ast.Name,
    ast.Load, ast.Attribute, ast.GeneratorExp, ast.ListComp, ast.comprehension, ast.Store, ast.Subscript,
    ast.List, ast.Tuple, ast.IfExp, ast.And, ast.Or, ast.Not, ast.USub, ast.UAdd, ast.Add, ast.Sub,
    ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.FloorDiv, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt,
    ast.GtE, ast.Index if hasattr(ast, "Index") else ast.Constant,
)
_BINDING_SOURCES = ("api:", "ui:", "const:")


def build_links(parsed: Dict[str, Any]) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []

    def add(src: str, targets: Any, relation: str) -> None:
        for t in targets if isinstance(targets, list) else [targets]:
            if t:
                links.append({"from_key": src, "to_key": t, "relation": relation})

    for f in parsed["formulas"]:
        add(f["key"], f.get("verifies", []), "verifies")
    for fl in parsed["flows"]:
        add(fl["key"], fl.get("covers", []), "covers")
        add(fl["key"], fl.get("checks", []), "checks")
    for ec in parsed["edge_cases"]:
        add(ec["key"], ec.get("covers", []), "covers")
        add(ec["key"], ec.get("checks", []), "checks")
        add(ec["key"], ec.get("applies_to", ""), "applies_to")
    for ux in parsed["ux_rules"]:
        add(ux["key"], ux.get("covers", []), "covers")
    for g in parsed["gotchas"]:
        add(g["key"], g.get("applies_to", ""), "applies_to")
    return links


def _formula_problems(item: Dict[str, Any]) -> List[str]:
    rule = item.get("rule", "")
    if not rule:
        return [f"{item['key']}: formula has no rule"]
    try:
        tree = ast.parse(rule, mode="eval")
    except SyntaxError as exc:
        return [f"{item['key']}: rule does not parse ({exc.msg})"]

    problems: List[str] = []
    local: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.comprehension):
            for t in ast.walk(node.target):
                if isinstance(t, ast.Name):
                    local.add(t.id)
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            problems.append(f"{item['key']}: '{type(node).__name__}' is not allowed in formulas")
            break
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            problems.append(f"{item['key']}: private attribute '{node.attr}' is not allowed")
        if isinstance(node, ast.Call):
            if not (isinstance(node.func, ast.Name) and node.func.id in FORMULA_FUNCTIONS):
                problems.append(f"{item['key']}: only {sorted(FORMULA_FUNCTIONS)} may be called")
    bindings = set(item.get("bindings", {}))
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - FORMULA_FUNCTIONS - local - called
    for missing in sorted(names - bindings):
        problems.append(f"{item['key']}: variable '{missing}' has no binding")
    for var, spec in item.get("bindings", {}).items():
        if not spec.startswith(_BINDING_SOURCES):
            problems.append(f"{item['key']}: binding '{var}={spec}' must start with api:, ui: or const:")
    return problems


def _ux_problems(item: Dict[str, Any]) -> List[str]:
    key, check = item["key"], item.get("check", "")
    if check not in UX_CHECK_TYPES:
        return [f"{key}: unknown check type '{check}' (use one of {sorted(UX_CHECK_TYPES)})"]
    problems: List[str] = []
    required = {"consistent_value": ["targets"], "format": ["targets", "pattern"],
                "max_wait": ["max_ms"], "judged": ["question"]}.get(check, [])
    problems += [f"{key}: check '{check}' needs field '{f}'" for f in required if not item.get(f)]
    if check == "consistent_value" and len(item.get("targets", [])) < 2:
        problems.append(f"{key}: consistent_value needs at least two targets")
    if check == "format" and item.get("pattern"):
        try:
            re.compile(item["pattern"])
        except re.error as exc:
            problems.append(f"{key}: pattern does not compile ({exc})")
    if check == "max_wait" and item.get("max_ms") and not str(item["max_ms"]).isdigit():
        problems.append(f"{key}: max_ms must be a whole number of milliseconds")
    return problems


def validate_playbook(parsed: Dict[str, Any], previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    errors: List[str] = list(parsed.get("parse_errors", []))
    warnings: List[str] = []

    keys: Dict[str, int] = {}
    for item in parsed["items"]:
        keys[item["key"]] = keys.get(item["key"], 0) + 1
    errors += [f"{k}: ID is defined {n} times" for k, n in keys.items() if n > 1]

    # references must resolve
    flow_keys = {f["key"] for f in parsed["flows"]}
    all_keys = set(keys)
    for link in parsed["links"]:
        target = link["to_key"]
        if link["relation"] == "applies_to":
            ok = target in flow_keys
        else:
            ok = target in all_keys
        if not ok:
            errors.append(f"{link['from_key']}: {link['relation']} '{target}' does not exist")

    for f in parsed["formulas"]:
        errors += _formula_problems(f)
    for ux in parsed["ux_rules"]:
        errors += _ux_problems(ux)
        if ux.get("severity") and ux["severity"] not in SEVERITIES:
            errors.append(f"{ux['key']}: severity '{ux['severity']}' is not one of {sorted(SEVERITIES)}")
    for r in parsed["requirements"]:
        if r.get("priority") and r["priority"] not in PRIORITIES:
            warnings.append(f"{r['key']}: unknown priority '{r['priority']}'")
        if not r.get("acceptance"):
            warnings.append(f"{r['key']}: requirement has no acceptance criteria")
    for fl in parsed["flows"]:
        if not fl["steps"] and not fl.get("goal"):
            errors.append(f"flow {fl['key']}: needs a goal or steps")
    for ec in parsed["edge_cases"]:
        if not ec.get("expect"):
            errors.append(f"{ec['key']}: edge case needs an 'expect' line")
    for rx in parsed["reasoning_examples"]:
        for scope in rx.get("scope", []):
            if scope not in RX_SCOPES:
                warnings.append(f"{rx['key']}: unknown scope '{scope}'")

    # unknown fields and sections
    for item in parsed["items"]:
        extra = set(item["body"]) - KNOWN_FIELDS.get(item["category"], set()) \
            - ({"steps", "expect", "test_data", "goal"} if item["category"] == "flow" else set())
        warnings += [f"{item['key']}: unknown field '{f}'" for f in sorted(extra)]
    warnings += [f"unknown section '{s}'" for s in parsed["unknown_sections"]]

    coverage = requirement_coverage(parsed)
    warnings += [f"{r}: requirement is not covered by any flow, formula or edge case"
                 for r in coverage["uncovered"]]

    if previous:
        old = {f["key"] for f in previous.get("flows", [])}
        gone, new = old - flow_keys, flow_keys - old
        if gone and new:
            warnings.append(f"flow renamed? {sorted(gone)} -> {sorted(new)}; its history will split")

    return {"errors": errors, "warnings": warnings, "coverage": coverage}
