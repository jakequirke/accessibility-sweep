"""WCAG 2.2 success criteria lookup from wcag-sc.json."""

import json
from pathlib import Path

from accessibility_sweep.models import Issue

_JSON_PATH = Path(__file__).resolve().parent.parent / "wcag-sc.json"

# Flat lookup maps built once on import
_BY_ID: dict[str, dict] = {}
_BY_AXE_RULE: dict[str, dict] = {}

# Manual mapping for axe best-practice rules that aren't formally tagged
# with a WCAG SC but clearly relate to one.
_AXE_BEST_PRACTICE_MAP = {
    "empty-heading": "2.4.6",       # Headings and Labels
    "heading-order": "1.3.1",       # Info and Relationships
    "label-title-only": "3.3.2",    # Labels or Instructions
    "aria-dialog-name": "4.1.2",    # Name, Role, Value
    "region": "1.3.1",              # Info and Relationships
    "skip-link": "2.4.1",           # Bypass Blocks
    "tabindex": "2.4.3",            # Focus Order
    "meta-viewport": "1.4.4",       # Resize Text
    "landmark-one-main": "1.3.1",   # Info and Relationships
    "landmark-no-duplicate-main": "1.3.1",
    "landmark-banner-is-top-level": "1.3.1",
    "landmark-contentinfo-is-top-level": "1.3.1",
    "landmark-main-is-top-level": "1.3.1",
    "landmark-unique": "1.3.1",
    "page-has-heading-one": "1.3.1",
    "table-fake-caption": "1.3.1",
    "scope-attr-valid": "1.3.1",
    "frame-title-unique": "4.1.2",
    "identical-links-same-purpose": "3.2.4",  # Consistent Identification
}


def _load() -> None:
    global _BY_ID, _BY_AXE_RULE
    if _BY_ID:
        return
    with open(_JSON_PATH) as f:
        data = json.load(f)
    for principle in data["principles"]:
        for guideline in principle["guidelines"]:
            for sc in guideline["success_criteria"]:
                _BY_ID[sc["id"]] = sc
                if sc.get("axe_rule"):
                    _BY_AXE_RULE[sc["axe_rule"]] = sc

    # Add best-practice mappings (don't overwrite JSON-sourced entries)
    for rule, sc_id in _AXE_BEST_PRACTICE_MAP.items():
        if rule not in _BY_AXE_RULE and sc_id in _BY_ID:
            _BY_AXE_RULE[rule] = _BY_ID[sc_id]


_load()


def by_id(sc_id: str) -> dict | None:
    """Look up a success criterion by its ID (e.g. '1.4.3')."""
    return _BY_ID.get(sc_id)


def by_axe_rule(rule_id: str) -> dict | None:
    """Reverse lookup: axe rule name -> success criterion."""
    return _BY_AXE_RULE.get(rule_id)


def enrich_issue(issue: Issue) -> Issue:
    """Fill wcag_name and wcag_level from the lookup. Mutates and returns the issue."""
    sc = by_id(issue.wcag_criterion)
    if sc:
        issue.wcag_name = sc["name"]
        issue.wcag_level = sc["level"]
    return issue
