from typing import Any, Dict, Optional

from qagent.decision.claude import BedrockClient
from qagent.playbooks.parser import parse_playbook_markdown

FORMAT_GUIDE = """Rewrite the freeform test description into this exact Markdown playbook format:

# Playbook: <title>
base_url: <url>

## Flow: <kebab-case-key>
Severity: <critical|high|medium|low>

### Steps
1. Open /path            (navigation steps must be exactly 'Open /path' or 'Go to /path')
2. Click <visible label> / Enter the <field> / Add <n> items to cart

### Expect
- <observable outcome>

### Test data
- key: value

### Formulas   (only when the text states an arithmetic or consistency rule)
- name: `python expression`
  - kind: formula|dom
  - bindings: var=api:/path.field, var=ui:<css selector>, var=const:<value>

### Edge cases
- <case>

Never invent selectors, URLs or rules that are not implied by the text. Omit sections with no content."""

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
    warnings = list(parsed["warnings"])
    if not parsed["flows"]:
        warnings.append("normalized output contains no flows")
    for flow in parsed["flows"]:
        if not flow["steps"]:
            warnings.append(f"flow '{flow['key']}' has no steps")
    return {
        "markdown": markdown,
        "parsed": parsed,
        "warnings": warnings,
        "notes": out["input"].get("notes"),
        "usage": out["usage"],
    }
