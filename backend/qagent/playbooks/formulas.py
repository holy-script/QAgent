from typing import Any, Dict, Optional
from simpleeval import SimpleEval, NameNotDefined


def evaluate_formula(expression: str, context: Dict[str, Any]) -> bool:
    """
    Evaluates a deterministic Python-like formula expression using simpleeval.
    Never uses an LLM for formulas.
    Returns True if assertion/formula holds, False otherwise.
    """
    evaluator = SimpleEval(names=context)
    # Add safe helper builtins like round, sum, min, max, len, abs
    evaluator.functions = {
        "round": round,
        "sum": sum,
        "min": min,
        "max": max,
        "len": len,
        "abs": abs,
    }
    
    try:
        result = evaluator.eval(expression)
        return bool(result)
    except Exception as e:
        return False
