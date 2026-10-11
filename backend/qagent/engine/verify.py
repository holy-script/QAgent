import json
import uuid
import re
from typing import Any, Dict, List
from urllib.parse import urljoin

from playwright.async_api import Page

from qagent.domain.runspec import FlowSpec
from qagent.domain.schemas import Finding
from qagent.engine.findings import Verifier

_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_API_SPEC = re.compile(r"^(/[^.]*)(?:\.(.+))?$")


class BindingError(Exception):
    pass


def parse_number(text: str) -> Any:
    """'$1,234.50' -> 1234.5; text without a number is returned unchanged."""
    match = _NUMBER.search(text)
    if not match:
        return text.strip()
    num = match.group(0).replace(",", "")
    return float(num) if "." in num else int(num)


def _drill(data: Any, dotted: str) -> Any:
    for part in dotted.split("."):
        if isinstance(data, dict) and part in data:
            data = data[part]
        else:
            raise BindingError(f"field '{dotted}' not found in API response")
    return data


async def resolve_binding(page: Page, base_url: str, spec: str) -> Any:
    """
    Binding forms:  api:/path.field   ui:<css selector>   const:<value>
    api bindings are fetched live through the browser context (shared cookies), so
    they reflect server state at verification time rather than whatever the UI cached.
    """
    kind, _, rest = spec.partition(":")
    if kind == "const":
        try:
            return json.loads(rest)
        except ValueError:
            return rest
    if kind == "ui":
        try:
            text = await page.locator(rest).first.inner_text(timeout=2000)
        except Exception as exc:
            raise BindingError(f"UI element {rest} not found on {page.url}") from exc
        return parse_number(text)
    if kind == "api":
        match = _API_SPEC.match(rest)
        if not match:
            raise BindingError(f"bad api binding '{spec}'")
        path, field = match.groups()
        try:
            resp = await page.context.request.get(urljoin(base_url, path), timeout=5000)
            data = await resp.json()
        except Exception as exc:
            raise BindingError(f"API {path} unreachable: {exc}") from exc
        return _drill(data, field) if field else data
    raise BindingError(f"unknown binding source '{kind}' in '{spec}'")


async def verify_flow_formulas(
    page: Page, base_url: str, flow: FlowSpec, step_seq: int, flow_run_id: str
) -> List[Finding]:
    """Evaluates every playbook formula against the flow's final state."""
    findings: List[Finding] = []
    for name, formula in flow.formulas.items():
        expr = formula["expr"] if isinstance(formula, dict) else str(formula)
        bindings: Dict[str, str] = formula.get("bindings", {}) if isinstance(formula, dict) else {}
        kind = formula.get("kind", "formula") if isinstance(formula, dict) else "formula"

        context: Dict[str, Any] = {}
        try:
            for var, spec in bindings.items():
                context[var] = await resolve_binding(page, base_url, spec)
        except BindingError as exc:
            findings.append(Finding(
                id=f"find-{uuid.uuid4().hex[:12]}",
                flow_run_id=flow_run_id,
                step_seq=step_seq,
                severity="medium",
                kind="dom" if kind == "dom" else "formula",
                title=f"Check could not be evaluated: {name}",
                expected=expr,
                actual=str(exc),
                evidence={"name": name, "bindings": bindings},
            ))
            continue

        finding = Verifier.check_formula(name, expr, context, step_seq, flow_run_id, kind=kind)
        if finding:
            findings.append(finding)
    return findings
