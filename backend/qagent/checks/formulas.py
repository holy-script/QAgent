import ast
from typing import Any, Dict

from qagent.checks.base import CheckOutcome
from qagent.checks.resolver import BindingError, BindingResolver
from qagent.playbooks.formulas import evaluate_formula_strict


def _within_tolerance(rule: str, context: Dict[str, Any], tolerance: float) -> bool:
    """For `lhs == rhs` rules, accept |lhs - rhs| <= tolerance."""
    tree = ast.parse(rule, mode="eval").body
    if not (isinstance(tree, ast.Compare) and len(tree.ops) == 1 and isinstance(tree.ops[0], ast.Eq)):
        return False
    lhs = evaluate_formula_value(ast.unparse(tree.left), context)
    rhs = evaluate_formula_value(ast.unparse(tree.comparators[0]), context)
    return abs(float(lhs) - float(rhs)) <= tolerance


def evaluate_formula_value(expression: str, context: Dict[str, Any]) -> Any:
    from simpleeval import EvalWithCompoundTypes
    from qagent.playbooks.formulas import wrap_attr
    ev = EvalWithCompoundTypes(names={k: wrap_attr(v) for k, v in context.items()})
    ev.functions = {"round": round, "sum": sum, "min": min, "max": max, "len": len, "abs": abs}
    return ev.eval(expression)


async def run_formula(item: Dict[str, Any], resolver: BindingResolver, severity: str, step_seq: int) -> CheckOutcome:
    key, rule = item["key"], item["rule"]
    inputs: Dict[str, Any] = {}
    context: Dict[str, Any] = {}
    try:
        for var, spec in item.get("bindings", {}).items():
            got = await resolver.resolve(spec)
            context[var] = got["value"]
            inputs[var] = {k: v for k, v in got.items() if k != "data"}
    except BindingError as exc:
        return CheckOutcome(
            key=key, kind="formula", passed=False, severity="medium", title=f"{key} could not be evaluated",
            expected=rule, actual=str(exc), inputs=inputs, requirement_keys=item.get("verifies", []),
            finding_kind="formula", locus=_locus(item),
        )

    try:
        ok = evaluate_formula_strict(rule, context)
        tol = float(item["tolerance"]) if item.get("tolerance") else 0.0
        if not ok and tol:
            ok = _within_tolerance(rule, context, tol)
        actual = "holds" if ok else f"false for {context}"
    except Exception as exc:
        ok, actual = False, f"{type(exc).__name__}: {exc}"

    return CheckOutcome(
        key=key, kind="formula", passed=ok, severity=severity,
        title=f"{key} {item.get('title', '')} failed".replace("  ", " "),
        expected=rule, actual=actual, inputs=inputs, requirement_keys=item.get("verifies", []),
        finding_kind="formula", locus=_locus(item), evidence={"context": context, "formula": rule},
    )


def _locus(item: Dict[str, Any]) -> str:
    for spec in item.get("bindings", {}).values():
        if spec.startswith("ui:"):
            return spec[3:]
    return ""
