"""Turns a product document into a HIGH-LEVEL test plan: journeys described by a goal, not click-by-click steps."""
import re
from typing import Any, Dict, List, Optional

from qagent.decision.claude import BedrockClient
from qagent.playbooks.normalize import FORMAT_GUIDE, NORMALIZE_TOOL
from qagent.playbooks.parser import parse_playbook_markdown

MAX_PRD_CHARS = 150_000

INSTRUCTIONS = """You are writing a HIGH-LEVEL test plan from a product requirements document (PRD), for an automated tester that works out the
individual clicks itself. Follow the format below exactly.

What to write:
- Requirements: the testable statements the PRD makes (REQ-1, REQ-2, ...). Quote or closely paraphrase the PRD; give each acceptance
  criteria and a priority taken from the PRD's own emphasis (default high). Do not add requirements the PRD does not state.
- Flows: one per major user journey the PRD describes (about 3 to 8). Each flow has:
    * `#### Goal`: ONE or TWO sentences on what the user is trying to accomplish, at the level of a person describing a task
      ("Sign in, then complete the forecast setup and reach the results"). Include preconditions in words (for example "sign in first").
    * `#### Expect`: 2 to 5 observable outcomes that prove the goal was achieved (what the page shows), not internal details.
    * `#### Test data`: ONLY values the tester must type that the PRD cannot know (for example `username: <fill in>`,
      `password: <fill in>`). Use exactly `<fill in>` as the value so the author sees what is missing. Omit the section if nothing is needed.
    * NEVER write a `#### Steps` section, click-by-click instructions, selectors or URLs (unless the PRD names a URL).
- Edge cases (about 3 to 6): important failure or boundary situations the PRD implies (invalid input, missing data, permissions),
  each tied to a flow with `applies_to`, an `expect` line, and test_data overrides only when needed.
- Gotchas: only behaviours the PRD itself describes that could look like bugs. Skip the section otherwise.
- Skip Formulas, UX rules and reasoning examples unless the PRD states an exact calculation or rule.
- Use only what the PRD says. If something important is unclear, still write the flow but keep the goal general, and mention the gap in `notes`.
"""

_PLACEHOLDER = re.compile(r"<[^>]*fill[^>]*>", re.IGNORECASE)


def _guide() -> str:
    # The shared format guide, minus its "rewrite freeform text" framing line.
    body = FORMAT_GUIDE.split("\n", 2)[-1]
    return INSTRUCTIONS + "\nFormat:\n" + body


async def plan_from_prd(prd: str, base_url: str, client: Optional[BedrockClient] = None) -> Dict[str, Any]:
    client = client or BedrockClient()
    user = f"Application address: {base_url}\n\nProduct requirements document:\n{prd[:MAX_PRD_CHARS]}"
    out = await client.converse_tool(_guide(), user, NORMALIZE_TOOL, max_tokens=8000, timeout=300.0)
    markdown = out["input"]["markdown"]
    parsed = parse_playbook_markdown(markdown)
    warnings: List[str] = list(parsed["errors"]) + list(parsed["warnings"])
    if not parsed["flows"]:
        warnings.append("the plan contains no journeys")
    for flow in parsed["flows"]:
        if not flow.get("goal") and not flow["steps"]:
            warnings.append(f"flow '{flow['key']}' has neither a goal nor steps")
        missing = [k for k, v in (flow.get("test_data") or {}).items() if _PLACEHOLDER.search(str(v))]
        if missing:
            warnings.append(f"fill in the test data for '{flow['key']}': {', '.join(missing)} (it is typed in as written)")
    return {"markdown": markdown, "parsed": parsed, "warnings": warnings, "notes": out["input"].get("notes"), "usage": out.get("usage", {})}
