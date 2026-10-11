import httpx
import pytest
import respx

from qagent.browser.sandbox import BrowserSandbox
from qagent.checks.a11y import a11y_rule
from qagent.decision.claude import BedrockClient
from qagent.playbooks.prd_extract import extract_requirements, requirements_markdown
from qagent.playbooks.parser import parse_playbook_markdown

PRD = """# Checkout PRD
## 3.2 Pricing
The cart total must apply the discount before tax. Totals are rounded to two decimals.
## 4.1 Address
Checkout requires a valid postal code and shows an inline error when it is missing.
"""


@pytest.mark.asyncio
async def test_axe_a11y_rule_flags_missing_alt_and_passes_clean_page():
    sb = BrowserSandbox()
    page = await sb.start()
    try:
        await page.set_content('<html lang="en"><head><title>t</title></head><body><main><img src="data:,x"></main></body></html>')
        bad = await a11y_rule({"key": "UX-9", "title": "No a11y violations"}, page)
        assert not bad.passed and "image-alt" in bad.actual and bad.finding_kind == "dom"
        await page.set_content('<html lang="en"><head><title>t</title></head><body><main><h1>Hi</h1></main></body></html>')
        assert (await a11y_rule({"key": "UX-9"}, page)).passed
    finally:
        await sb.stop()


@pytest.mark.asyncio
@respx.mock
async def test_prd_extraction_drops_proposals_whose_quote_is_not_in_the_prd():
    proposals = [
        {"title": "Discount before tax", "prd_ref": "3.2 Pricing", "acceptance": "total = (subtotal - discount) * 1.08",
         "priority": "high", "quote": "apply the discount before tax"},
        {"title": "Invented", "prd_ref": "9.9", "acceptance": "x", "priority": "low", "quote": "never said this"},
        {"title": "Postal code", "prd_ref": "4.1 Address", "acceptance": "inline error", "priority": "high",
         "quote": "shows an inline error when it is missing"},
    ]
    respx.post(url__regex=r".*/converse").mock(return_value=httpx.Response(200, json={
        "output": {"message": {"content": [{"toolUse": {"name": "x", "input": {"requirements": proposals}}}]}},
        "usage": {"inputTokens": 1, "outputTokens": 1}}))
    got = await extract_requirements(PRD, existing_keys=["REQ-1", "REQ-2"],
                                     client=BedrockClient(api_key="k", region="us-east-1", model_id="m"))
    assert [p["key"] for p in got] == ["REQ-3", "REQ-4"] and [p["title"] for p in got] == ["Discount before tax", "Postal code"]
    md = requirements_markdown(got)
    parsed = parse_playbook_markdown("# Playbook: x\n\n## Requirements\n" + md)
    assert [r["key"] for r in parsed["requirements"]] == ["REQ-3", "REQ-4"] and parsed["errors"] == []


def test_redact_body_masks_configured_keys_recursively():
    import json
    from qagent.browser.redact import redact_body
    body = json.dumps({"email": "a@b.c", "items": [{"id": 1, "Card": {"number": "4111"}}], "ok": True}).encode()
    out = json.loads(redact_body(body, ["email", "card"]))
    assert out == {"email": "[redacted]", "items": [{"id": 1, "Card": "[redacted]"}], "ok": True}
    assert redact_body(b"<html>", ["email"]) == b"<html>" and redact_body(body, []) == body
