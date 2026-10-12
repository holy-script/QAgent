from typing import Any, Dict, Optional

from qagent.decision.claude import BedrockClient
from qagent.playbooks.parser import parse_playbook_markdown

FORMAT_GUIDE = """Rewrite the freeform test description into this exact Markdown playbook format. Omit sections
with no content, and never invent selectors, URLs or rules the text does not imply.

# Playbook: <title>
base_url: <url>

## Requirements
### REQ-1: <testable statement>
- prd_ref: <section>
- acceptance: <criteria>
- priority: critical|high|medium|low

## Formulas
### F-1: <name>
- rule: `python expression over bound variables`
- bindings: var=api:/path.field, var=ui:<css selector>, var=const:<value>
- verifies: REQ-1

## UX rules
### UX-1: <title>
- check: consistent_value | format | max_wait | no_console_errors | judged
- (targets / pattern / max_ms / question depending on the check)
- severity: medium

## Edge cases
### EC-1: <title>
- applies_to: <flow key>
- expect: <expected behaviour>
- covers: REQ-1
- test_data: key=value

## Flows
### Flow: <kebab-case-key>
- covers: REQ-1
- checks: F-1, UX-1
- severity: high

#### Goal                 (use INSTEAD of Steps for a high-level journey: the tester works out the clicks itself)
One or two sentences: what the user is trying to accomplish.

#### Steps               (optional when there is a Goal; a suggested route)
1. Open /path            (navigation steps must be exactly 'Open /path' or 'Go to /path')
2. Click <visible label> / Enter the <field> / Add <n> items to cart

#### Expect
- <observable outcome>

#### Test data
- key: value"""

NORMALIZE_TOOL = {
    "toolSpec": {
        "name": "emit_playbook",
        "description": "Return the normalized playbook Markdown.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {"markdown": {"type": "string"}, "notes": {"type": "string", "description": "assumptions made"}},
            "required": ["markdown"],
        }},
    }
}


async def normalize_playbook(raw: str, client: Optional[BedrockClient] = None) -> Dict[str, Any]:
    """Claude rewrites freeform text into canonical playbook Markdown; the result is re-parsed and validated."""
    client = client or BedrockClient()
    out = await client.converse_tool(FORMAT_GUIDE, raw, NORMALIZE_TOOL, max_tokens=2048)
    markdown = out["input"]["markdown"]
    parsed = parse_playbook_markdown(markdown)
    warnings = list(parsed["errors"]) + list(parsed["warnings"])
    if not parsed["flows"]:
        warnings.append("normalized output contains no flows")
    for flow in parsed["flows"]:
        if not flow["steps"] and not flow.get("goal"):
            warnings.append(f"flow '{flow['key']}' has no steps")
    return {
        "markdown": markdown,
        "parsed": parsed,
        "warnings": warnings,
        "notes": out["input"].get("notes"),
        "usage": out["usage"],
    }
