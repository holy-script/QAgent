import re
from typing import Any, Dict, List, Optional

from qagent.checks.base import CheckOutcome
from qagent.checks.resolver import BindingError, BindingResolver


async def consistent_value(item: Dict[str, Any], resolver: BindingResolver) -> CheckOutcome:
    key = item["key"]
    inputs: Dict[str, Any] = {}
    values: List[Any] = []
    try:
        for i, spec in enumerate(item["targets"]):
            got = await resolver.resolve(spec)
            values.append(got["value"])
            inputs[f"target_{i + 1}"] = {k: v for k, v in got.items() if k != "data"}
    except BindingError as exc:
        return CheckOutcome(key=key, kind="ux_rule", passed=False, severity="medium", finding_kind="dom",
                            title=f"{key} could not be evaluated", expected="all targets equal",
                            actual=str(exc), inputs=inputs, locus=_first_ui(item))
    ok = all(v == values[0] for v in values)
    return CheckOutcome(
        key=key, kind="ux_rule", passed=ok, severity=item.get("severity", "medium"), finding_kind="dom",
        title=f"{key} {item.get('title', '')} violated", expected="all targets show the same value",
        actual="equal" if ok else " vs ".join(f"{t}={v}" for t, v in zip(item["targets"], values)),
        inputs=inputs, requirement_keys=item.get("covers", []), locus=_first_ui(item),
        evidence={"values": values, "targets": item["targets"]},
    )


async def format_rule(item: Dict[str, Any], resolver: BindingResolver) -> CheckOutcome:
    key, pattern = item["key"], re.compile(item["pattern"])
    inputs: Dict[str, Any] = {}
    bad: List[str] = []
    seen = 0
    try:
        for spec in item["targets"]:
            if spec.startswith("ui:"):
                texts = await resolver.ui_all(spec[3:])
            else:
                texts = [str((await resolver.resolve(spec))["value"])]
            inputs[spec] = {"values": texts}
            seen += len(texts)
            bad += [t for t in texts if not pattern.fullmatch(t)]
    except BindingError as exc:
        return CheckOutcome(key=key, kind="ux_rule", passed=False, severity="medium", finding_kind="dom",
                            title=f"{key} could not be evaluated", expected=item["pattern"], actual=str(exc),
                            locus=_first_ui(item))
    return CheckOutcome(
        key=key, kind="ux_rule", passed=not bad, severity=item.get("severity", "low"), finding_kind="dom",
        title=f"{key} {item.get('title', '')} violated", expected=f"matches {item['pattern']}",
        actual=("no matching elements on this page" if seen == 0 else f"{len(bad)} mismatched: {bad[:5]}") if bad or seen == 0
        else f"{seen} values match", inputs=inputs, locus=_first_ui(item), requirement_keys=item.get("covers", []),
    )


def max_wait(item: Dict[str, Any], settles: List[Dict[str, Any]]) -> CheckOutcome:
    """settles: [{'step_seq', 'settle_ms', 'settled'}] recorded during the flow."""
    limit = float(item["max_ms"])
    worst = max(settles, key=lambda s: s["settle_ms"], default=None)
    violations = [s for s in settles if not s["settled"] or s["settle_ms"] > limit]
    ok = not violations
    step_seq = (violations[0]["step_seq"] if violations else (worst["step_seq"] if worst else 1))
    return CheckOutcome(
        key=item["key"], kind="ux_rule", passed=ok, severity=item.get("severity", "high"), finding_kind="timing",
        title=f"{item['key']} {item.get('title', '')} violated", expected=f"no wait longer than {limit:.0f}ms",
        actual="all waits within limit" if ok else
        f"step {violations[0]['step_seq']} still busy after {violations[0]['settle_ms']:.0f}ms"
        + ("" if not violations[0]["settled"] else " (settled late)"),
        inputs={"settles": settles}, requirement_keys=item.get("covers", []),
        locus="loading-indicator", evidence={"step_seq": step_seq, "max_ms": limit},
    )


def no_console_errors(item: Dict[str, Any], console: List[Dict[str, Any]], ignore: List[str]) -> CheckOutcome:
    errors = [c for c in console if c["type"] in ("error", "pageerror")
              and not any(re.search(p, c["text"]) for p in ignore)]
    return CheckOutcome(
        key=item["key"], kind="ux_rule", passed=not errors, severity=item.get("severity", "medium"),
        finding_kind="dom", title=f"{item['key']} {item.get('title', '')} violated",
        expected="no console errors", actual="clean" if not errors else f"{len(errors)} errors: {errors[0]['text'][:120]}",
        inputs={"errors": [e["text"][:200] for e in errors[:10]]}, locus="console",
        requirement_keys=item.get("covers", []),
    )


def _first_ui(item: Dict[str, Any]) -> str:
    for t in item.get("targets", []):
        if t.startswith("ui:"):
            return t[3:]
    return ""
