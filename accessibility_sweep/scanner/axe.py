import re

from playwright.sync_api import sync_playwright, Page
from axe_playwright_python.sync_playwright import Axe

from accessibility_sweep.models import Issue, PageResult, Severity
from accessibility_sweep import wcag_lookup

AXE_IMPACT_MAP = {
    "critical": Severity.CRITICAL,
    "serious": Severity.MAJOR,
    "moderate": Severity.MAJOR,
    "minor": Severity.MINOR,
}

# Regex to match axe criterion tags like "wcag111" -> "1.1.1", "wcag2411" -> "2.4.11"
_CRITERION_RE = re.compile(r"^wcag(\d)(\d)(\d+)$")


def _parse_wcag_criterion(tags: list[str]) -> str:
    """Extract a WCAG criterion reference (e.g. '1.4.3') from axe-core tags."""
    for tag in tags:
        m = _CRITERION_RE.match(tag)
        if m:
            return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
    return ""


def _axe_violation_to_issues(violation: dict) -> list[Issue]:
    """Convert a single axe violation (which may have multiple nodes) into Issues."""
    issues = []
    severity = AXE_IMPACT_MAP.get(violation.get("impact", "minor"), Severity.MINOR)
    wcag_tags = [t for t in violation.get("tags", []) if t.startswith("wcag")]
    wcag_criterion = _parse_wcag_criterion(wcag_tags)

    # Fallback: use wcag-sc.json reverse lookup if tag parsing found nothing
    if not wcag_criterion:
        sc = wcag_lookup.by_axe_rule(violation["id"])
        if sc:
            wcag_criterion = sc["id"]

    # Prefer WCAG understanding doc URL over axe helpUrl
    sc = wcag_lookup.by_id(wcag_criterion) if wcag_criterion else None
    help_text = violation.get("help", violation.get("description", ""))
    if sc:
        recommendation = f"{help_text} — {sc['url']}"
    else:
        recommendation = help_text

    for node in violation.get("nodes", []):
        target = ", ".join(node.get("target", []))
        issues.append(Issue(
            type=violation["id"],
            element=target or violation["id"],
            description=violation.get("description", violation.get("help", "")),
            wcag_criterion=wcag_criterion,
            severity=severity,
            recommendation=recommendation,
            source="axe",
        ))
    return issues


class AxeScanner:
    """Run axe-core against a Playwright page."""

    def scan(self, url: str) -> PageResult:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)

            axe = Axe()
            results = axe.run(page)

            html = page.content()
            browser.close()

        issues = []
        for violation in results.response.get("violations", []):
            issues.extend(_axe_violation_to_issues(violation))

        return PageResult(url=url, issues=issues), html

    def scan_page(self, page: Page, url: str) -> tuple[PageResult, str]:
        """Scan an already-open Playwright page (avoids re-launching browser)."""
        axe = Axe()
        results = axe.run(page)
        html = page.content()

        issues = []
        for violation in results.response.get("violations", []):
            issues.extend(_axe_violation_to_issues(violation))

        return PageResult(url=url, issues=issues), html
