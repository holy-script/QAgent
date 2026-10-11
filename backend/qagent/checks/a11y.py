from pathlib import Path
from typing import Any, Dict, List

import axe_playwright_python
from playwright.async_api import Page

from qagent.checks.base import CheckOutcome

_AXE_JS = (Path(axe_playwright_python.__file__).parent / "axe.min.js").read_text(encoding="utf-8")
_SEVERITY = {"critical": "high", "serious": "high", "moderate": "medium", "minor": "low"}
_ORDER = ["minor", "moderate", "serious", "critical"]


async def run_axe(page: Page) -> List[Dict[str, Any]]:
    """Injects axe-core (bundled, no network) and returns its violations for the current page."""
    await page.add_script_tag(content=_AXE_JS)
    result = await page.evaluate("async () => await axe.run(document)")
    return result.get("violations", [])


async def a11y_rule(item: Dict[str, Any], page: Page) -> CheckOutcome:
    """Fails when axe reports violations at or above the rule's `impact` (default: moderate)."""
    floor = _ORDER.index(item.get("impact", "moderate")) if item.get("impact", "moderate") in _ORDER else 1
    try:
        violations = await run_axe(page)
    except Exception as exc:
        return CheckOutcome(key=item["key"], kind="ux_rule", passed=False, severity="low", finding_kind="dom",
                            title=f"{item['key']} could not be evaluated", expected="axe-core scan completes",
                            actual=f"{type(exc).__name__}: {exc}"[:200], locus="a11y")
    relevant = [v for v in violations if _ORDER.index(v.get("impact") or "minor") >= floor]
    worst = max((v["impact"] for v in relevant), key=_ORDER.index, default=None)
    return CheckOutcome(
        key=item["key"], kind="ux_rule", passed=not relevant,
        severity=_SEVERITY.get(worst, "medium") if worst else item.get("severity", "medium"), finding_kind="dom",
        title=f"{item['key']} {item.get('title', '')} violated", expected="no accessibility violations",
        actual="clean" if not relevant else "; ".join(f"{v['id']} ({v['impact']}, {len(v['nodes'])} nodes)" for v in relevant[:5]),
        inputs={"violations": [{"id": v["id"], "impact": v["impact"], "help": v["help"],
                                "targets": [n["target"] for n in v["nodes"][:3]]} for v in relevant[:10]]},
        requirement_keys=item.get("covers", []), locus="a11y",
        evidence={"violation_ids": [v["id"] for v in relevant]},
    )
