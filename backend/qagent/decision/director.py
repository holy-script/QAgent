"""
The director: for a journey described by a goal ("sign in and set up a forecast"), Claude looks at the live page and
chooses the next single step, one at a time, until the goal is reached or it is blocked. The step it writes is an
ordinary test step ("Click Sign in", "Enter the username"); the fast AI then picks the element and the engine acts,
checks and records it exactly as it does for a hand-written step. Values are never invented: typed text comes from
the journey's test data, matched by field name.
"""
import json
from typing import Any, Dict, List, Optional

from qagent.domain.schemas import CandidateAction

NEXT_STEP_TOOL = {
    "toolSpec": {
        "name": "next_step",
        "description": "Choose the next single step toward the goal, or say the goal is reached or blocked.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["continue", "done", "blocked"]},
                "intent": {"type": "string", "description": "the next step, one action, in plain words (empty unless status is continue)"},
                "why": {"type": "string", "description": "one short sentence: what you see and why this step (or why done/blocked)"},
            },
            "required": ["status", "why"],
        }},
    }
}

SYSTEM = (
    "You direct an automated QA tester who is working towards a goal in a web app, one action at a time. You see the "
    "current page and what has been done so far. Choose the next single step, or say the goal is reached, or say you are blocked.\n"
    "Write the step the way a test step is written, in plain words, one action only: 'Click <visible label>', "
    "'Enter the <field name>', 'Select <option> in <field name>', 'Open /path'. For typing, only say which field "
    "('Enter the username'); the value is filled in automatically from the test data, so never write or invent values.\n"
    "Rules: do not repeat a step that worked unless the page shows it did not take effect; do not wander off the goal; "
    "answer 'done' only when the page shows the goal has been achieved (or the final state described in the expected "
    "outcomes); answer 'blocked' only when the page shows an error or a missing capability that prevents any further "
    "progress, and say what you see."
)


def build_prompt(goal: str, expect: List[str], route: List[str], test_fields: List[str], history: List[Dict[str, Any]],
                 url: str, title: str, page_text: str, candidates: List[CandidateAction]) -> str:
    past = "\n".join(
        f"{i}. {h.get('intent')} -> {h.get('action') or '?'} [{h.get('status', 'ok')}]" for i, h in enumerate(history[-8:], 1)
    ) or "(nothing yet: this is the first step)"
    elements = "\n".join(f"[{c.id}] <{c.tag}> {c.label!r} ({c.action_type})" for c in candidates[:40]) or "(no interactive elements)"
    return (
        f"Goal: {goal}\n"
        + (f"Expected outcomes when finished: {'; '.join(expect)}\n" if expect else "")
        + (f"Suggested route (optional, follow only if it fits what you see): {'; '.join(route)}\n" if route else "")
        + f"Test data fields available for typing: {', '.join(test_fields) or '(none)'}\n\n"
        + f"Steps so far:\n{past}\n\n"
        + f"Current page: {url}\nTitle: {title}\nVisible text (excerpt):\n{page_text[:1800]}\n\n"
        + f"Interactive elements:\n{elements}"
    )


async def next_step(client: Any, goal: str, expect: List[str], route: List[str], test_data: Dict[str, Any],
                    history: List[Dict[str, Any]], url: str, title: str, page_text: str,
                    candidates: List[CandidateAction], examples: Optional[List[Dict[str, Any]]] = None) -> Dict[str, str]:
    """-> {"status": continue|done|blocked, "intent": str, "why": str}"""
    system = SYSTEM
    if examples:
        from qagent.decision.fewshot import render_examples
        system += "\n\nHow to reason about tricky situations:\n" + render_examples(examples)
    prompt = build_prompt(goal, expect, route, sorted(test_data), history, url, title, page_text, candidates)
    out = await client.converse_tool(system, prompt, NEXT_STEP_TOOL, max_tokens=300)
    a = out["input"]
    status = a.get("status") if a.get("status") in ("continue", "done", "blocked") else "blocked"
    intent = str(a.get("intent", "")).strip()
    if status == "continue" and not intent:
        status = "blocked"
    return {"status": status, "intent": intent, "why": str(a.get("why", "")).strip()}
