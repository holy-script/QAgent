from typing import Any, Dict, List, Sequence


def steps_to_reproduce(steps: Sequence[Any], up_to_seq: int, test_data: Dict[str, Any]) -> List[str]:
    """
    Numbered steps built purely from the recorded steps (intent + the element actually used).
    Never written by a model, so it can be trusted to match what the agent did.
    """
    lines: List[str] = []
    for st in sorted(steps, key=lambda s: s.seq):
        if st.seq > up_to_seq:
            break
        label = (st.action_label or "").strip()
        if label.startswith("Navigate to "):
            lines.append(f"Open {label[len('Navigate to '):]}")
        elif label and not label.startswith("("):
            lines.append(f'{st.intent} (element: "{label}")')
        else:
            lines.append(st.intent)
    out = [f"{i}. {text}" for i, text in enumerate(lines, 1)]
    if test_data:
        out.append("Test data: " + ", ".join(f"{k}={v}" for k, v in test_data.items()))
    return out
