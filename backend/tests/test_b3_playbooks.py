from pathlib import Path

import pytest

from qagent.checks.edge_cases import expand_flows
from qagent.playbooks.coverage import requirement_coverage
from qagent.playbooks.formulas import evaluate_formula
from qagent.playbooks.parser import parse_playbook_markdown

PLAYBOOK = Path(__file__).parents[2] / "playbooks" / "checkout.md"


def parse(extra_replace=None):
    text = PLAYBOOK.read_text(encoding="utf-8")
    for old, new in (extra_replace or []):
        assert old in text, old
        text = text.replace(old, new)
    return parse_playbook_markdown(text)


def test_sample_playbook_parses_all_seven_categories():
    p = parse()
    assert (p["title"], p["base_url"], p["prd"]) == ("Checkout", "http://localhost:8001", "PRD-checkout-v2")
    assert [len(p[k]) for k in ("requirements", "formulas", "ux_rules", "gotchas", "edge_cases", "flows",
                                "reasoning_examples")] == [3, 1, 4, 2, 2, 4, 1]
    assert p["errors"] == [] and p["warnings"] == []

    f1 = p["formulas"][0]
    assert f1["verifies"] == ["REQ-1"] and f1["tolerance"] == "0.01"
    assert f1["bindings"]["total"] == "ui:[data-testid=cart-total]" and f1["bindings"]["tax_rate"] == "const:0.08"
    ux4 = next(u for u in p["ux_rules"] if u["key"] == "UX-4")
    assert ux4["pattern"] == r"^\$\d{1,3}(,\d{3})*\.\d{2}$" and len(ux4["targets"]) == 2
    assert p["gotchas"][0]["wait_for"] == "api:/api/cart/add"
    rx = p["reasoning_examples"][0]
    assert rx["scope"] == ["escalation", "judge"] and len(rx["strategy"]) == 4
    flow = p["flows"][0]
    assert flow["steps"][1] == "Add 2 items to cart" and flow["checks"] == ["F-1", "UX-1", "UX-4"]
    assert {(l["from_key"], l["to_key"], l["relation"]) for l in p["links"]} >= {
        ("F-1", "REQ-1", "verifies"), ("add-to-cart", "UX-1", "checks"), ("EC-3", "checkout", "applies_to")}


def test_edge_cases_expand_into_flow_variants():
    flows = {f.key: f for f in expand_flows(parse())}
    assert {"add-to-cart", "apply-coupon", "payment", "checkout", "apply-coupon#EC-2", "checkout#EC-3"} == set(flows)
    v = flows["checkout#EC-3"]
    assert v.variant_of == "checkout" and v.test_data == {"postal": "<empty>"}
    assert v.checks == ["UX-3"] and v.expect == ["An inline error appears and the address is not saved."]
    assert [f.key for f in expand_flows(parse(), include_edge_cases=False)] == [
        "add-to-cart", "apply-coupon", "payment", "checkout"]
    assert [f.key for f in expand_flows(parse(), ["checkout"])] == ["checkout", "checkout#EC-3"]


def test_requirement_coverage_and_uncovered_warning():
    p = parse()
    assert requirement_coverage(p)["covered_by"]["REQ-2"] == ["payment"]
    uncovered = parse([("- covers: REQ-2\n- severity: critical", "- severity: critical")])
    assert any("REQ-2" in w and "not covered" in w for w in uncovered["warnings"])
    assert uncovered["errors"] == []


@pytest.mark.parametrize("replace,expected", [
    ([("### REQ-2:", "### REQ-1:")], "REQ-1: ID is defined 2 times"),
    ([("- verifies: REQ-1", "- verifies: REQ-9")], "REQ-9' does not exist"),
    ([("(1 + tax_rate)", "(1 + tax_rate + shipping)")], "variable 'shipping' has no binding"),
    ([("round((sum", "open((sum")], "only ['abs'"),
    ([("- check: max_wait\n- max_ms: 2500", "- check: wobble")], "unknown check type 'wobble'"),
    ([("- check: max_wait\n- max_ms: 2500", "- check: max_wait")], "needs field 'max_ms'"),
    ([("- pattern: ^\\$", "- pattern: ^(\\$")], "pattern does not compile"),
    ([("- applies_to: checkout", "- applies_to: nowhere")], "'nowhere' does not exist"),
])
def test_validation_errors_block(replace, expected):
    errors = parse(replace)["errors"]
    assert any(expected in e for e in errors), errors


def test_unknown_section_and_field_are_warnings_and_rename_is_flagged():
    p = parse([("- severity: low\n\n## Gotchas", "- severity: low\n- colour: red\n\n## Gotchas"),
               ("## Gotchas", "## Mystery\n### G-9: x\n- note: y\n\n## Gotchas")])
    assert any("unknown section 'Mystery'" in w for w in p["warnings"])
    assert any("UX-4: unknown field 'colour'" in w for w in p["warnings"])
    old = parse()
    renamed = parse_playbook_markdown(
        PLAYBOOK.read_text().replace("### Flow: payment", "### Flow: pay-now"), previous=old)
    assert any("renamed" in w for w in renamed["warnings"])


def test_evaluate_formula_success_and_failure():
    formula = "total == round(subtotal * (1 + tax_rate), 2)"
    assert evaluate_formula(formula, {"total": 108.0, "subtotal": 100.0, "tax_rate": 0.08}) is True
    assert evaluate_formula(formula, {"total": 115.0, "subtotal": 100.0, "tax_rate": 0.08}) is False
    assert evaluate_formula("sum(i.qty for i in items) == 3", {"items": [{"qty": 1}, {"qty": 2}]}) is True
