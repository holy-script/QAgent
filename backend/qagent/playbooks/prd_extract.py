from typing import Any, Dict, List, Optional

from qagent.decision.claude import BedrockClient

EXTRACT_TOOL = {
    "toolSpec": {
        "name": "propose_requirements",
        "description": "Propose testable requirements found in the PRD.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {"requirements": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "One testable statement"},
                    "prd_ref": {"type": "string", "description": "Section heading or number the statement comes from"},
                    "acceptance": {"type": "string", "description": "Concrete, observable acceptance criteria"},
                    "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "quote": {"type": "string", "description": "Short verbatim quote from the PRD that supports it"},
                },
                "required": ["title", "prd_ref", "acceptance", "priority", "quote"],
            }}},
            "required": ["requirements"],
        }},
    }
}

SYSTEM = ("You extract testable requirements from a product requirements document for a QA team. Propose only what "
          "the document states or directly implies, one statement per requirement, with observable acceptance "
          "criteria. Quote the supporting text verbatim. Do not invent requirements.")


async def extract_requirements(prd: str, existing_keys: Optional[List[str]] = None,
                               client: Optional[BedrockClient] = None) -> List[Dict[str, Any]]:
    """
    Claude proposes requirements; code keeps only proposals whose quote really appears in the PRD, assigns
    REQ- IDs that do not collide with existing ones, and leaves acceptance to the user (one by one).
    """
    client = client or BedrockClient()
    out = await client.converse_tool(SYSTEM, prd[:40000], EXTRACT_TOOL, max_tokens=3000)
    haystack = " ".join(prd.split()).lower()
    taken = {int(k.split("-")[1]) for k in (existing_keys or []) if k.startswith("REQ-") and k.split("-")[1].isdigit()}
    n = max(taken, default=0)
    proposals: List[Dict[str, Any]] = []
    for req in out["input"].get("requirements", []):
        quote = " ".join(str(req.get("quote", "")).split()).lower()
        if not quote or quote not in haystack:
            continue  # unsupported by the PRD text: dropped
        n += 1
        proposals.append({"key": f"REQ-{n}", "title": req["title"], "prd_ref": req["prd_ref"],
                          "acceptance": req["acceptance"], "priority": req["priority"], "quote": req["quote"]})
    return proposals


def requirements_markdown(proposals: List[Dict[str, Any]]) -> str:
    return "\n".join(
        f"### {p['key']}: {p['title']}\n- prd_ref: {p['prd_ref']}\n- acceptance: {p['acceptance']}\n"
        f"- priority: {p['priority']}\n" for p in proposals)
