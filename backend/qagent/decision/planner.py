"""The planner: before a journey runs, Claude reads its steps once and writes a short note per step
(what to look for, what could go wrong). The notes become hints for the step decisions; the steps themselves
are never rewritten, so the test stays exactly what the author wrote. The call is on the tape, so a repeat is identical."""
import json
from typing import Any, Dict, List, Optional

from qagent.decision.charter import with_charter
from qagent.decision.fewshot import example_ids, render_examples

PLAN_TOOL = {
    "toolSpec": {
        "name": "plan_flow",
        "description": "Write a short note for each step of a QA journey.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "One sentence: what this journey proves"},
                "steps": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "step": {"type": "integer", "description": "1-based step number"},
                        "look_for": {"type": "string", "description": "What the page element probably looks like"},
                        "caution": {"type": "string", "description": "What could make this step ambiguous or fail; empty if nothing"},
                    },
                    "required": ["step", "look_for"],
                }},
            },
            "required": ["summary", "steps"],
        }},
    }
}

SYSTEM = ("You help an automated browser tester prepare a journey through a web app. For each step, say in one short "
          "phrase what the target element probably looks like and anything that could be ambiguous. Do not change, add "
          "or remove steps. Use only what the steps and test data say. If the target may not be a real button (a card, row, icon "
          "or plain text), say so in the note.")


def step_hints(plan: Dict[str, Any], steps: int) -> Dict[int, str]:
    """step number -> one-line hint, ignoring anything outside the real step range."""
    out: Dict[int, str] = {}
    for item in plan.get("steps", []) or []:
        try:
            n = int(item.get("step"))
        except (TypeError, ValueError):
            continue
        if 1 <= n <= steps:
            text = f"Look for: {str(item.get('look_for', '')).strip()}"
            if str(item.get("caution", "")).strip():
                text += f". Careful: {str(item['caution']).strip()}"
            out[n] = text
    return out


async def plan_flow(client: Any, flow_key: str, steps: List[str], base_url: str, test_data: Dict[str, Any],
                    examples: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    system = with_charter(SYSTEM) + ("\n\nHow to reason about tricky situations:\n" + render_examples(examples) if examples else "")
    listing = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    user = (f"App: {base_url}\nJourney: {flow_key}\nTest data: {json.dumps(test_data, sort_keys=True, default=str)[:1500]}\n"
            f"Steps:\n{listing}")
    out = await client.converse_tool(system, user, PLAN_TOOL, max_tokens=900)
    return {**out["input"], "few_shot_ids": example_ids(examples or [])}
