"""
Keyboard navigation persona.

Claude tabs through the page like a keyboard-only user, checking:
- Skip-to-content link is first focusable element
- All interactive elements are reachable via Tab
- Focus indicators are clearly visible
- Dropdown/flyout menus are keyboard-accessible
- Focus order follows logical reading sequence
- No keyboard traps
- Enter/Space activate controls correctly
- Focus not obscured by sticky elements (WCAG 2.4.11)
"""

import json
from pathlib import Path

from playwright.sync_api import Page

from accessibility_sweep.models import Issue
from accessibility_sweep.agent.core import run_persona
from accessibility_sweep.agent.tools import KEYBOARD_TOOLS

_ARIA_PATTERNS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "reference" / "aria_patterns.json"


SYSTEM_PROMPT = """\
You are a keyboard-only user testing this web page. You cannot use a mouse. \
You must navigate exclusively using press_key. You cannot click anything.

You have CPACC certification and deep expertise in WCAG 2.2 AA keyboard \
requirements and the ARIA Authoring Practices Guide.

## Your testing procedure

1. **Check for a skip link** by first calling get_focusable_elements to \
see the full tab order, then pressing Tab once from the top of the page.
   - If a skip link exists, activate it with Enter and verify focus moves \
past the navigation.
   - If no skip link exists, log an issue against WCAG 2.4.1 Bypass Blocks.

2. **Tab through every interactive element** on the page sequentially. \
For each element that receives focus, call get_focus_state and check:
   - Is the focus indicator visible (has_outline or has_box_shadow)?
   - Is the accessible name meaningful (not empty, not "click here")?
   - Is the role appropriate for the element's purpose?
   - Is the element obscured behind sticky headers/footers (is_obscured)?
   - Record the focus order sequence as you go.

3. **At each interactive widget** (dropdown, modal trigger, tab panel, \
accordion, carousel):
   - Test the expected keyboard pattern from the ARIA Authoring Practices. \
If ARIA pattern data was provided, use it to know exactly which keys to test.
   - For modals: verify focus moves into the modal, is trapped inside, \
Escape closes it, and focus returns to the trigger.
   - For dropdowns: verify Arrow keys move between options, Enter/Space \
selects, Escape closes.
   - For tab panels: verify Arrow keys move between tabs, the selected \
panel is shown.

4. **After completing the tab sequence:**
   - Compare your recorded focus order against the DOM-order list of \
interactive elements from get_focusable_elements.
   - Flag any interactive elements you could not reach.
   - Flag any illogical order (e.g. focus jumps from header to footer, \
skipping main content).

5. **Test reverse tab order** (Shift+Tab) from the last element back \
through several elements. Confirm it is the reverse of the forward order.

6. **Check the accessibility tree** with get_accessibility_tree if you \
need to verify widget roles or understand the page structure.

## WCAG criteria to evaluate

- 2.1.1 Keyboard — Can every interactive element be reached and operated?
- 2.1.2 No Keyboard Trap — Can the user always move focus away?
- 2.4.1 Bypass Blocks — Is there a skip link or equivalent mechanism?
- 2.4.3 Focus Order — Does tab order match visual/logical reading order?
- 2.4.7 Focus Visible — Is there a visible focus indicator on every element?
- 2.4.11 Focus Not Obscured (Minimum) — Is focused element at least \
partially visible (not behind sticky headers/modals)?
- 2.4.12 Focus Not Obscured (Enhanced) — Is focused element fully visible?
- 3.2.1 On Focus — Does anything unexpected happen when an element receives focus?

## Important rules

- Tab through AT LEAST 15-20 elements to get good coverage.
- Always call get_focus_state after press_key to see what happened.
- If you suspect a dropdown or menu, try ArrowDown / Enter to open it.
- If focus seems stuck, try Escape, then Shift+Tab, before declaring a trap.
- You have a limited number of tool calls — be thorough but efficient.

## Severity guide

- critical: user cannot complete a core task (keyboard trap, unreachable \
form submit, unreachable navigation)
- major: significant barrier but workaround exists (missing skip link, \
poor focus order, focus obscured by sticky header)
- minor: usable but degraded experience (weak focus indicator, slightly \
illogical order, minor focus appearance issue)

## Output format

When you have completed your testing, respond with a JSON object (no markdown \
fencing, no preamble):
{
  "issues": [
    {
      "type": "string — one of: skip_link_missing, skip_link_broken, \
focus_not_visible, focus_order_illogical, keyboard_trap, \
element_not_keyboard_accessible, dropdown_not_keyboard_accessible, \
focus_obscured, focus_indicator_insufficient, interactive_not_reachable, \
unexpected_focus_change",
      "element": "CSS selector or description of the element",
      "description": "Detailed explanation: what you observed, why it is a \
barrier, and who it affects",
      "wcag_criterion": "e.g. 2.4.7",
      "severity": "critical | major | minor",
      "recommendation": "Specific fix with code examples where helpful",
      "visual_location": "Where on the page this element is"
    }
  ],
  "summary": "Overall keyboard accessibility assessment"
}"""


def _load_aria_patterns() -> str:
    """Load ARIA widget keyboard patterns for context."""
    try:
        with open(_ARIA_PATTERNS_PATH) as f:
            data = json.load(f)
        # Summarise the patterns concisely
        lines = []
        for role, info in data.items():
            keys = ", ".join(f"{k}: {v}" for k, v in info.get("expected_keyboard", {}).items())
            lines.append(f"- {role}: {keys}")
        return "\n".join(lines)
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


def run(page: Page, url: str, axe_findings: list[dict] | None = None) -> list[Issue]:
    """Run the keyboard navigation persona against a page."""
    context_parts = [
        f"Test the keyboard accessibility of this page: {url}\n",
        "Start by listing all focusable elements, then tab through the page "
        "systematically. Check for a skip-to-content link, visible focus "
        "indicators, logical focus order, keyboard-accessible widgets, "
        "focus not obscured by sticky elements, and keyboard traps.\n",
    ]

    # Include axe findings so the persona knows what's already flagged
    if axe_findings:
        context_parts.append(
            "The following issues were already found by automated scanning "
            "(do NOT re-report these, focus on what automation missed):\n"
            + json.dumps(axe_findings[:20], indent=2)[:3000] + "\n"
        )

    # Include ARIA pattern reference
    aria_patterns = _load_aria_patterns()
    if aria_patterns:
        context_parts.append(
            "ARIA widget keyboard patterns (test these when you encounter "
            "the corresponding widget roles):\n" + aria_patterns + "\n"
        )

    initial_message = "\n".join(context_parts)

    return run_persona(
        page=page,
        url=url,
        system_prompt=SYSTEM_PROMPT,
        tools=KEYBOARD_TOOLS,
        initial_message=initial_message,
        persona_name="keyboard",
    )
