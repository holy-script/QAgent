import re
import hashlib
from typing import Dict, Any, List
from markdown_it import MarkdownIt
from qagent.domain.runspec import FlowSpec


def parse_playbook_markdown(content: str) -> Dict[str, Any]:
    """
    Parses a Markdown playbook (such as playbooks/checkout-flow.md)
    into structured metadata, flows, steps, expectations, formulas, and edge cases.
    """
    md = MarkdownIt()
    tokens = md.parse(content)

    title = "Playbook"
    base_url = "http://localhost:8001"
    flows: List[FlowSpec] = []
    warnings: List[str] = []

    current_flow: Dict[str, Any] = {}
    current_section = ""

    lines = content.splitlines()
    for line in lines:
        line_strip = line.strip()
        if line_strip.startswith("# Playbook:"):
            title = line_strip.replace("# Playbook:", "").strip()
        elif line_strip.startswith("base_url:"):
            base_url = line_strip.replace("base_url:", "").strip()
        elif line_strip.startswith("## Flow:"):
            if current_flow:
                flows.append(FlowSpec.model_validate(current_flow))
            flow_key = line_strip.replace("## Flow:", "").strip()
            current_flow = {
                "key": flow_key,
                "severity": "high",
                "steps": [],
                "expect": [],
                "test_data": {},
                "formulas": {},
                "edge_cases": []
            }
            current_section = ""
        elif line_strip.startswith("Severity:"):
            if current_flow:
                current_flow["severity"] = line_strip.replace("Severity:", "").strip().lower()
        elif line_strip.startswith("### Steps"):
            current_section = "steps"
        elif line_strip.startswith("### Expect"):
            current_section = "expect"
        elif line_strip.startswith("### Test data"):
            current_section = "test_data"
        elif line_strip.startswith("### Formulas"):
            current_section = "formulas"
        elif line_strip.startswith("### Edge cases"):
            current_section = "edge_cases"
        elif current_flow:
            if current_section == "steps" and re.match(r"^\d+\.\s*", line_strip):
                step_text = re.sub(r"^\d+\.\s*", "", line_strip)
                current_flow["steps"].append(step_text)
            elif current_section == "expect" and line_strip.startswith("- "):
                current_flow["expect"].append(line_strip[2:].strip())
            elif current_section == "test_data" and line_strip.startswith("- "):
                kv = line_strip[2:].split(":", 1)
                if len(kv) == 2:
                    current_flow["test_data"][kv[0].strip()] = kv[1].strip()
            elif current_section == "formulas" and line_strip.startswith("- "):
                # e.g. - cart_total: `total == ...`
                match = re.match(r"^-\s*([a-zA-Z0-9_]+):\s*`([^`]+)`", line_strip)
                if match:
                    current_flow["formulas"][match.group(1)] = match.group(2)
            elif current_section == "edge_cases" and line_strip.startswith("- "):
                current_flow["edge_cases"].append(line_strip[2:].strip())

    if current_flow:
        flows.append(FlowSpec.model_validate(current_flow))

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    return {
        "title": title,
        "base_url": base_url,
        "flows": [f.model_dump() for f in flows],
        "warnings": warnings,
        "content_hash": content_hash,
    }
