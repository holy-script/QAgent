from typing import Any, Dict, List, Optional

from qagent.checks.base import CheckOutcome, max_severity
from qagent.checks.ux_judged import Judge, Verdict


def judged_outcome(key: str, kind: str, statement: str, verdict: Verdict, severity: str,
                   requirement_keys: List[str], title: str, locus: str = "") -> CheckOutcome:
    """Judged findings are labeled with who judged and capped at medium severity."""
    capped = severity if severity in ("low", "info", "medium") else "medium"
    return CheckOutcome(
        key=key, kind=kind, passed=verdict.passed, severity=capped, finding_kind="dom", title=title,
        expected=statement, actual="true" if verdict.passed else f"false ({verdict.reasoning or 'judged not true'})",
        inputs={"judged_by": verdict.judged_by, "probability": round(verdict.probability, 3),
                "reasoning": verdict.reasoning, "few_shot_ids": verdict.few_shot_ids or []},
        judged_by=verdict.judged_by, confidence=verdict.confidence, requirement_keys=requirement_keys, locus=locus,
    )


async def run_expectation(judge: Judge, flow_key: str, n: int, text: str, severity: str, requirement_keys: List[str],
                          page_text: str, screenshots: List[bytes], hints: List[str],
                          examples: List[Dict[str, Any]]) -> CheckOutcome:
    verdict = await judge.ask(f"On this page, is the following true: {text}", page_text, screenshots, hints, examples)
    return judged_outcome(f"expect:{flow_key}:{n}", "expectation", text, verdict, severity, requirement_keys,
                          f"Expectation not met: {text}")


async def run_judged_rule(judge: Judge, item: Dict[str, Any], page_text: str, screenshots: List[bytes],
                          hints: List[str], examples: List[Dict[str, Any]]) -> CheckOutcome:
    verdict = await judge.ask(item["question"], page_text, screenshots, hints, examples)
    sev = max_severity(item.get("severity", "medium"), "low")
    return judged_outcome(item["key"], "ux_judged", item["question"], verdict, sev, item.get("covers", []),
                          f"{item['key']} {item.get('title', '')} violated")
