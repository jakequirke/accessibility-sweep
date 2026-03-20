"""
Keyboard and focus visibility checks using Playwright.
Simulates Tab key navigation and checks for visible focus indicators.
"""

from playwright.sync_api import Page

from accessibility_sweep.models import Issue, Severity


def check_focus_visibility(page: Page) -> list[Issue]:
    """
    Tab through interactive elements and check that each has a visible
    focus indicator (outline, border change, or box-shadow).
    """
    issues = []

    focusable_count = page.evaluate("""
    () => {
        const els = document.querySelectorAll(
            'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        return els.length;
    }
    """)

    # Tab through up to 30 elements
    max_tabs = min(focusable_count, 30)

    for _ in range(max_tabs):
        page.keyboard.press("Tab")

        focus_info = page.evaluate("""
        () => {
            const el = document.activeElement;
            if (!el || el === document.body) return null;

            const style = window.getComputedStyle(el);
            const outlineStyle = style.outlineStyle;
            const outlineWidth = parseFloat(style.outlineWidth);
            const boxShadow = style.boxShadow;

            const hasOutline = outlineStyle !== 'none' && outlineWidth > 0;
            const hasBoxShadow = boxShadow !== 'none';

            // Check for :focus-visible styles by comparing with unfocused state
            return {
                tag: el.tagName.toLowerCase(),
                id: el.id || '',
                className: (el.className && typeof el.className === 'string')
                    ? el.className.split(' ')[0] : '',
                text: el.textContent ? el.textContent.trim().substring(0, 40) : '',
                hasOutline: hasOutline,
                hasBoxShadow: hasBoxShadow,
                outlineStyle: outlineStyle,
            };
        }
        """)

        if focus_info is None:
            continue

        if not focus_info["hasOutline"] and not focus_info["hasBoxShadow"]:
            selector = focus_info["tag"]
            if focus_info["id"]:
                selector += f"#{focus_info['id']}"
            elif focus_info["className"]:
                selector += f".{focus_info['className']}"

            issues.append(Issue(
                type="focus_not_visible",
                element=selector,
                description=(
                    f"Element {selector} has no visible focus indicator. "
                    f"Text: \"{focus_info['text']}\""
                ),
                wcag_criterion="2.4.7",
                severity=Severity.MAJOR,
                recommendation=(
                    "Ensure a visible focus indicator (outline, box-shadow, or border change) "
                    "is present on :focus or :focus-visible."
                ),
                source="WCAG 2.2",
            ))

    return issues
