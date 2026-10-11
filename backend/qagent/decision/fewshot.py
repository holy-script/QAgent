import hashlib
import json
import re
from typing import Any, Dict, List, Sequence


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3}


def example_hash(example: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(example, sort_keys=True, default=str).encode()).hexdigest()[:12]


def select_examples(examples: Sequence[Dict[str, Any]], scope: str, text: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Up to `limit` reasoning examples whose scope includes `scope`, ranked by keyword overlap with `text`
    (flow + step). Ties keep playbook order, so selection is deterministic.
    """
    wanted = _words(text)
    scored = []
    for order, ex in enumerate(examples):
        if scope not in ex.get("scope", []):
            continue
        body = " ".join([ex.get("title", ""), ex.get("context", "")] + list(ex.get("strategy", [])))
        scored.append((-len(wanted & _words(body)), order, ex))
    return [ex for _, _, ex in sorted(scored, key=lambda t: (t[0], t[1]))[:limit]]


def render_examples(examples: Sequence[Dict[str, Any]]) -> str:
    out = []
    for ex in examples:
        steps = "\n".join(f"  {i}. {s}" for i, s in enumerate(ex.get("strategy", []), 1))
        out.append(f"Example {ex['key']} - {ex.get('title', '')}\nSituation: {ex.get('context', '')}\nApproach:\n{steps}")
    return "\n\n".join(out)


def example_ids(examples: Sequence[Dict[str, Any]]) -> List[str]:
    """IDs with content hashes, recorded on the tape so replay knows exactly what the model saw."""
    return [f"{ex['key']}@{example_hash(ex)}" for ex in examples]
