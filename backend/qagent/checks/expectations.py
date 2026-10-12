import re
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


# Statements that can only be established by using the page (not by reading one screenshot of it).
NEEDS_INTERACTION = re.compile(
    r"\b(click\w*|tap\w*|hover\w*|respon\w+|interactive|navigat\w+|opens?|leads?|redirect\w*|submits?|toggle\w*|expand\w*|collaps\w*|"
    r"works?|working|functions?|functional|reachable|link\w*|buttons?|menus?|tabs?|dropdowns?|can be (used|selected|opened))\b", re.I)


async def run_expectation_live(judge: Any, flow_key: str, n: int, text: str, severity: str, requirement_keys: List[str],
                               page_text: str, screenshots: List[bytes], hints: List[str], examples: List[Dict[str, Any]],
                               page: Any, journey: str = "", console_logs: Optional[List[Dict[str, Any]]] = None,
                               state_js: Optional[str] = None, network_calls: Optional[List[Dict[str, Any]]] = None,
                               snapshots: Optional[List[Dict[str, Any]]] = None) -> Optional[CheckOutcome]:
    """An expectation checked with the live page when it needs it.
    Statements about things working go straight to the live verifier; the others get the quick judgement first, and a 'no'
    is double-checked live before it is reported (a screenshot cannot show that something does not work, or that it does).
    None means the live check stayed inconclusive: nothing is reported either way."""
    verify = bool(getattr(judge, "can_verify", False))
    question = f"On this page, is the following true: {text}"

    async def live() -> Optional[Verdict]:
        return await judge.verify(question, page_text, page, journey, hints, examples, console_logs, state_js, network_calls, snapshots)

    outcome: Optional[CheckOutcome] = None
    if verify and NEEDS_INTERACTION.search(text):
        try:
            verdict = await live()
            return None if verdict is None else judged_outcome(
                f"expect:{flow_key}:{n}", "expectation", text, verdict, severity, requirement_keys, f"Expectation not met: {text}")
        except LookupError:
            pass   # a repeat of a run recorded before live checks existed: use the recorded quick judgement
    outcome = await run_expectation(judge, flow_key, n, text, severity, requirement_keys, page_text, screenshots, hints, examples)
    if outcome.passed or not verify:
        return outcome
    try:
        verdict = await live()
    except LookupError:
        return outcome
    return None if verdict is None else judged_outcome(
        f"expect:{flow_key}:{n}", "expectation", text, verdict, severity, requirement_keys, f"Expectation not met: {text}")
