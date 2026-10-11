import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

from markdown_it import MarkdownIt

from qagent.playbooks.schema import BLOCK_FIELDS, ID_PREFIX, LIST_FIELDS, SECTION_CATEGORIES
from qagent.playbooks.validate import build_links, validate_playbook

_FIELD = re.compile(r"^-\s+([A-Za-z_][\w]*)\s*:\s*(.*)$")
_ITEM_HEADING = re.compile(r"^([A-Z]{1,3}-\d+)\s*:\s*(.*)$")
_FLOW_HEADING = re.compile(r"^Flow\s*:\s*(.+)$", re.IGNORECASE)
_BINDING_SPLIT = re.compile(r",\s*(?=[A-Za-z_]\w*\s*=)")


def _split_list(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _parse_pairs(value: str) -> Dict[str, str]:
    """'qty=0, coupon=X' -> {'qty': '0', 'coupon': 'X'}"""
    out: Dict[str, str] = {}
    for part in _BINDING_SPLIT.split(value):
        k, _, v = part.partition("=")
        if k.strip() and v.strip():
            out[k.strip()] = v.strip()
    return out


def _headings(content: str) -> List[Tuple[int, str, int]]:
    """(level, text, 0-based line) for each heading, via the markdown-it token stream."""
    tokens = MarkdownIt().parse(content)
    found: List[Tuple[int, str, int]] = []
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.map:
            found.append((int(tok.tag[1]), tokens[i + 1].content.strip(), tok.map[0]))
    return found


def _parse_fields(lines: List[str], category: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    i = 0
    while i < len(lines):
        m = _FIELD.match(lines[i].rstrip())
        i += 1
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if key in BLOCK_FIELDS:
            block: List[str] = []
            while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                text = re.sub(r"^\s*(?:\d+[.)]|[-*])\s*", "", lines[i]).strip()
                if text:
                    block.append(text)
                i += 1
            fields[key] = ([value] if value else []) + block
        elif key == "bindings":
            fields[key] = _parse_pairs(value)
        elif key == "test_data":
            fields[key] = _parse_pairs(value)
        elif key in LIST_FIELDS:
            fields[key] = _split_list(value)
        elif key == "rule":
            fields[key] = value.strip("`").strip()
        else:
            fields[key] = value.strip("`") if key in ("pattern", "check") else value
    return fields


def _parse_flow_body(lines: List[str]) -> Dict[str, Any]:
    """Flow body: '- field: value' lines, then '#### Steps / Expect / Test data' subsections."""
    flow: Dict[str, Any] = {"steps": [], "expect": [], "test_data": {}}
    head: List[str] = []
    section: Optional[str] = None
    for line in lines:
        s = line.strip()
        if s.startswith("####"):
            section = s.lstrip("#").strip().lower()
            continue
        if section is None:
            head.append(line)
        elif section == "steps":
            m = re.match(r"^\d+[.)]\s*(.+)$", s)
            if m:
                flow["steps"].append(m.group(1).strip())
        elif section == "expect" and s.startswith("- "):
            flow["expect"].append(s[2:].strip())
        elif section == "test data" and s.startswith("- "):
            k, _, v = s[2:].partition(":")
            if k.strip() and v.strip():
                flow["test_data"][k.strip()] = v.strip()
    flow.update(_parse_fields(head, "flow"))
    return flow


def parse_playbook_markdown(content: str, previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Parses a seven-category playbook (requirements, flows, formulas, UX rules, gotchas, edge cases,
    reasoning examples) into structured items, validates them, and derives the item links used for
    traceability. No LLM is involved.
    """
    lines = content.splitlines()
    headings = _headings(content)

    title, base_url, prd = "Playbook", "http://localhost:8001", None
    for line in lines:
        s = line.strip()
        if s.startswith("# Playbook:"):
            title = s.replace("# Playbook:", "", 1).strip()
        elif s.startswith("base_url:"):
            base_url = s.split(":", 1)[1].strip()
        elif s.startswith("prd:"):
            prd = s.split(":", 1)[1].strip()

    parsed: Dict[str, Any] = {
        "title": title, "base_url": base_url, "prd": prd,
        "requirements": [], "formulas": [], "ux_rules": [], "gotchas": [], "edge_cases": [],
        "flows": [], "reasoning_examples": [],
        "items": [], "unknown_sections": [], "parse_errors": [],
    }

    section_keys = {"requirement": "requirements", "formula": "formulas", "ux_rule": "ux_rules",
                    "gotcha": "gotchas", "edge_case": "edge_cases", "flow": "flows",
                    "reasoning_example": "reasoning_examples"}

    category: Optional[str] = None
    for idx, (level, text, line_no) in enumerate(headings):
        if level == 2:
            category = SECTION_CATEGORIES.get(text.lower())
            if category is None:
                parsed["unknown_sections"].append(text)
            continue
        if level != 3 or category is None:
            continue

        end = next((ln for lv, _, ln in headings[idx + 1:] if lv <= 3), len(lines))
        body = lines[line_no + 1:end]

        if category == "flow":
            m = _FLOW_HEADING.match(text)
            if not m:
                parsed["parse_errors"].append(f"flow heading must be 'Flow: <key>', got '{text}'")
                continue
            fields = _parse_flow_body(body)
            item = {"key": m.group(1).strip(), "title": m.group(1).strip(), "severity": "high",
                    "covers": [], "checks": [], **fields}
        else:
            m = _ITEM_HEADING.match(text)
            if not m or not m.group(1).startswith(ID_PREFIX[category]):
                parsed["parse_errors"].append(
                    f"heading '{text}' in '{category}' needs an ID like {ID_PREFIX[category]}1: Title")
                continue
            item = {"key": m.group(1), "title": m.group(2).strip(), **_parse_fields(body, category)}

        item["category"] = category
        parsed[section_keys[category]].append(item)
        parsed["items"].append({
            "key": item["key"], "category": category, "title": item["title"],
            "body": {k: v for k, v in item.items() if k not in ("key", "category", "title")},
        })

    parsed["links"] = build_links(parsed)
    report = validate_playbook(parsed, previous)
    parsed["errors"] = report["errors"]
    parsed["warnings"] = report["warnings"]
    parsed["coverage"] = report["coverage"]
    parsed["content_hash"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return parsed
