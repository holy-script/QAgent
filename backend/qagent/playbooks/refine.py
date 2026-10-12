"""Tidies up dictated (or rough) text. Claude rewrites it for a stated purpose and must not invent facts."""
from typing import Any, Dict, Optional

from qagent.decision.claude import BedrockClient

MAX_CHARS = 200_000

REFINE_TOOL = {
    "toolSpec": {
        "name": "emit_text",
        "description": "Return the rewritten text.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "the rewritten text"},
                "notes": {"type": "string", "description": "anything unclear that the author should check; empty if nothing"},
            },
            "required": ["text"],
        }},
    }
}

_COMMON = ("The input was dictated by voice or typed in a hurry, so it may have no punctuation, filler words ('um', 'like'), "
           "repetitions and misheard words. Use only what the author said: never invent features, numbers, names or rules. "
           "If something is unclear, keep it as said and mention it in `notes`.")

KINDS: Dict[str, str] = {
    "tidy": ("Fix punctuation, capitalisation and obvious mishearings, remove filler words and repetitions, and split into "
             "short paragraphs. Keep the author's own words and meaning. " + _COMMON),
    "description": ("Write a one or two sentence description of the app, in plain words, from what was said. " + _COMMON),
    "prd": ("Turn this into a clear product requirements document in Markdown with these sections (omit a section only if nothing "
            "was said about it): '# <product name or 'Product'>', '## Overview', '## Users', '## Features and requirements' "
            "(a numbered list; one testable statement each), '## Acceptance criteria', '## Out of scope', '## Open questions' "
            "(for anything unclear or contradictory). " + _COMMON),
    "notes": ("Turn this into a short bullet list of testing notes for an automated tester: how parts of the app behave, and "
              "things that look like bugs but are not. One bullet per note. " + _COMMON),
}


async def refine_text(text: str, kind: str, client: Optional[BedrockClient] = None) -> Dict[str, Any]:
    if kind not in KINDS:
        raise ValueError(f"unknown kind '{kind}'")
    client = client or BedrockClient()
    # A rewrite is about as long as its input, so the answer gets room to match (about 4 characters per token).
    max_tokens = min(32_000, max(3_000, len(text) // 3))
    out = await client.converse_tool(KINDS[kind], text[:MAX_CHARS], REFINE_TOOL, max_tokens=max_tokens, timeout=300.0)
    return {"text": out["input"]["text"], "notes": out["input"].get("notes") or None, "usage": out.get("usage", {})}
