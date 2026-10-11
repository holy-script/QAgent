import json
from typing import Any, Dict, List, Optional

from qagent.decision.claude import BedrockClient
from qagent.decision.fewshot import example_ids, render_examples, select_examples

RECOMMEND_TOOL = {
    "toolSpec": {
        "name": "recommend",
        "description": "Return recommendations grounded in the supplied facts.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {"recommendations": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["functional", "ux", "performance", "accessibility", "test_coverage"]},
                    "text": {"type": "string"},
                    "rationale": {"type": "string"},
                    "evidence_finding_ids": {"type": "array", "items": {"type": "string"}},
                    "requirement_keys": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "effort": {"type": "string", "enum": ["s", "m", "l"]},
                },
                "required": ["category", "text", "rationale", "evidence_finding_ids", "confidence", "effort"],
            }}},
            "required": ["recommendations"],
        }},
    }
}

BUG_NARRATIVE_TOOL = {
    "toolSpec": {
        "name": "bug_narrative",
        "description": "Describe the impact and a suspected cause of one bug, citing evidence IDs.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "impact": {"type": "string", "description": "1-3 sentences on who is affected and how"},
                "suspected_cause": {"type": "string", "description": "A hypothesis, phrased as such"},
                "cited_evidence_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["impact", "suspected_cause", "cited_evidence_ids"],
        }},
    }
}

SYSTEM = ("You write QA reports from a fact pack. Use only facts in the pack. Cite finding and evidence IDs exactly "
          "as given. Never invent IDs, requirements, URLs or numbers. Be concise and specific.")


async def recommend(client: BedrockClient, fact_pack: Dict[str, Any],
                    examples: List[Dict[str, Any]]) -> Dict[str, Any]:
    system = SYSTEM + ("\n\nHow to reason about tricky situations:\n" + render_examples(examples) if examples else "")
    out = await client.converse_tool(system, "Fact pack:\n" + json.dumps(fact_pack, default=str)[:30000],
                                     RECOMMEND_TOOL, max_tokens=2500)
    return {"recommendations": out["input"].get("recommendations", []), "usage": out["usage"],
            "few_shot_ids": example_ids(examples)}


async def bug_narrative(client: BedrockClient, facts: Dict[str, Any]) -> Dict[str, Any]:
    out = await client.converse_tool(SYSTEM, "Bug facts:\n" + json.dumps(facts, default=str)[:20000],
                                     BUG_NARRATIVE_TOOL, max_tokens=800)
    return out["input"]
