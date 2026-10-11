from pathlib import Path
import pytest
from qagent.playbooks.parser import parse_playbook_markdown
from qagent.playbooks.formulas import evaluate_formula


def test_parse_sample_checkout_flow():
    playbook_path = Path(__file__).parents[2] / "playbooks" / "checkout-flow.md"
    assert playbook_path.exists()
    content = playbook_path.read_text(encoding="utf-8")
    
    parsed = parse_playbook_markdown(content)
    assert parsed["title"] == "Checkout flow"
    assert parsed["base_url"] == "http://localhost:8001"
    assert len(parsed["flows"]) >= 1

    flow = parsed["flows"][0]
    assert flow["key"] == "add-to-cart"
    assert len(flow["steps"]) == 3
    assert flow["steps"][0] == "Open /products"
    assert "cart_total" in flow["formulas"]
    assert len(flow["edge_cases"]) == 2


def test_evaluate_formula_success():
    formula = "total == round(subtotal * (1 + tax_rate), 2)"
    context = {
        "total": 108.0,
        "subtotal": 100.0,
        "tax_rate": 0.08,
    }
    assert evaluate_formula(formula, context) is True


def test_evaluate_formula_failure():
    # Defect: tax calculated wrongly
    formula = "total == round(subtotal * (1 + tax_rate), 2)"
    context = {
        "total": 115.0,  # Incorrect total
        "subtotal": 100.0,
        "tax_rate": 0.08,
    }
    assert evaluate_formula(formula, context) is False
