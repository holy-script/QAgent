from typing import Any, Dict
from simpleeval import EvalWithCompoundTypes


class AttrDict(dict):
    """Dict that also exposes keys as attributes, so formulas can say `i.price`."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def wrap_attr(value: Any) -> Any:
    if isinstance(value, dict):
        return AttrDict({k: wrap_attr(v) for k, v in value.items()})
    if isinstance(value, list):
        return [wrap_attr(v) for v in value]
    return value


def evaluate_formula_strict(expression: str, context: Dict[str, Any]) -> bool:
    """
    Evaluates a deterministic Python-like formula using simpleeval (never an LLM).
    Raises if the expression is invalid or references an unbound name.
    """
    evaluator = EvalWithCompoundTypes(names={k: wrap_attr(v) for k, v in context.items()})
    evaluator.functions = {
        "round": round,
        "sum": sum,
        "min": min,
        "max": max,
        "len": len,
        "abs": abs,
    }
    return bool(evaluator.eval(expression))


def evaluate_formula(expression: str, context: Dict[str, Any]) -> bool:
    """Returns True if the formula holds; any evaluation error counts as False."""
    try:
        return evaluate_formula_strict(expression, context)
    except Exception:
        return False
