"""Playbook vocabulary: categories, ID prefixes, allowed fields and check types."""
from typing import Dict, Set

# "## Heading" -> category
SECTION_CATEGORIES: Dict[str, str] = {
    "requirements": "requirement",
    "flows": "flow",
    "formulas": "formula",
    "ux rules": "ux_rule",
    "gotchas": "gotcha",
    "edge cases": "edge_case",
    "reasoning examples": "reasoning_example",
}

ID_PREFIX: Dict[str, str] = {
    "requirement": "REQ-",
    "formula": "F-",
    "ux_rule": "UX-",
    "gotcha": "G-",
    "edge_case": "EC-",
    "reasoning_example": "RX-",
}

UX_CHECK_TYPES: Set[str] = {"consistent_value", "format", "max_wait", "no_console_errors", "a11y", "judged"}
SEVERITIES: Set[str] = {"critical", "high", "medium", "low", "info"}
PRIORITIES: Set[str] = {"critical", "high", "medium", "low"}
RX_SCOPES: Set[str] = {"planner", "escalation", "judge", "report"}
FORMULA_FUNCTIONS: Set[str] = {"sum", "round", "abs", "min", "max", "len"}

# Fields understood per category (anything else becomes a warning).
KNOWN_FIELDS: Dict[str, Set[str]] = {
    "requirement": {"prd_ref", "acceptance", "priority"},
    "formula": {"rule", "source", "bindings", "tolerance", "verifies"},
    "ux_rule": {"check", "targets", "pattern", "max_ms", "question", "severity", "covers", "ignore", "impact"},
    "gotcha": {"note", "wait_for", "ignore_console", "applies_to"},
    "edge_case": {"applies_to", "expect", "covers", "checks", "test_data"},
    "flow": {"covers", "checks", "severity", "role"},
    "reasoning_example": {"scope", "context", "challenge", "strategy"},
}

# Fields whose value is a comma-separated list of IDs / selectors.
LIST_FIELDS: Set[str] = {"covers", "checks", "verifies", "scope", "targets"}
# Fields whose value is a numbered list on following lines.
BLOCK_FIELDS: Set[str] = {"strategy"}
