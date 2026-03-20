"""
Custom structural accessibility checks: headings, landmarks, form labels.
Uses BeautifulSoup for HTML analysis.
"""

from bs4 import BeautifulSoup

from accessibility_sweep.models import Issue, Severity


def check_heading_structure(html: str) -> list[Issue]:
    """Check heading hierarchy: single h1, no skipped levels."""
    soup = BeautifulSoup(html, "html.parser")
    issues = []

    headings = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        level = int(tag.name[1])
        text = tag.get_text(strip=True)[:60]
        headings.append((level, text, tag.name))

    # Check for multiple h1s
    h1_count = sum(1 for level, _, _ in headings if level == 1)
    if h1_count == 0:
        issues.append(Issue(
            type="missing_h1",
            element="document",
            description="Page has no h1 element.",
            wcag_criterion="1.3.1",
            severity=Severity.MAJOR,
            recommendation="Add a single h1 element that describes the page's main topic.",
            source="WCAG 2.2",
        ))
    elif h1_count > 1:
        issues.append(Issue(
            type="multiple_h1",
            element="document",
            description=f"Page has {h1_count} h1 elements. Best practice is a single h1.",
            wcag_criterion="1.3.1",
            severity=Severity.MINOR,
            recommendation="Use a single h1 for the main page heading. Use h2+ for subsections.",
            source="WCAG 2.2",
        ))

    # Check for skipped levels
    for i in range(1, len(headings)):
        prev_level = headings[i - 1][0]
        curr_level = headings[i][0]
        if curr_level > prev_level + 1:
            issues.append(Issue(
                type="skipped_heading_level",
                element=headings[i][2],
                description=(
                    f"Heading level skipped: {headings[i-1][2]} \"{headings[i-1][1]}\" "
                    f"followed by {headings[i][2]} \"{headings[i][1]}\"."
                ),
                wcag_criterion="1.3.1",
                severity=Severity.MINOR,
                recommendation=f"Use an h{prev_level + 1} instead of {headings[i][2]}, or restructure the heading hierarchy.",
                source="WCAG 2.2",
            ))

    return issues


def check_landmarks(html: str) -> list[Issue]:
    """Check for required landmark regions."""
    soup = BeautifulSoup(html, "html.parser")
    issues = []

    required_landmarks = {
        "main": ("main", "[role='main']"),
        "nav": ("nav", "[role='navigation']"),
    }

    for name, (tag, role_selector) in required_landmarks.items():
        has_tag = soup.find(tag) is not None
        has_role = soup.select_one(role_selector) is not None
        if not has_tag and not has_role:
            issues.append(Issue(
                type=f"missing_landmark_{name}",
                element="document",
                description=f"Page is missing a <{tag}> landmark region.",
                wcag_criterion="1.3.1",
                severity=Severity.MAJOR,
                recommendation=f"Add a <{tag}> element (or role='{name}') to identify the {name} content area.",
                source="WCAG 2.2",
            ))

    return issues


def check_form_labels(html: str) -> list[Issue]:
    """Check that form inputs have associated labels."""
    soup = BeautifulSoup(html, "html.parser")
    issues = []

    inputs = soup.find_all(["input", "select", "textarea"])
    for inp in inputs:
        input_type = inp.get("type", "text")
        if input_type in ("hidden", "submit", "button", "reset", "image"):
            continue

        input_id = inp.get("id")
        has_label = False

        # Check for associated <label>
        if input_id:
            has_label = soup.find("label", attrs={"for": input_id}) is not None

        # Check for wrapping <label>
        if not has_label:
            has_label = inp.find_parent("label") is not None

        # Check for aria-label or aria-labelledby
        if not has_label:
            has_label = bool(inp.get("aria-label") or inp.get("aria-labelledby"))

        # Check for title attribute as last resort
        if not has_label:
            has_label = bool(inp.get("title"))

        if not has_label:
            name = inp.get("name", inp.get("id", inp.name))
            issues.append(Issue(
                type="missing_form_label",
                element=f"{inp.name}[name='{name}']" if inp.get("name") else inp.name,
                description=f"Form input '{name}' has no associated label.",
                wcag_criterion="1.3.1",
                severity=Severity.CRITICAL,
                recommendation="Add a <label for='...'> element, aria-label, or aria-labelledby attribute.",
                source="WCAG 2.2",
            ))

    return issues


def run_structure_checks(html: str) -> list[Issue]:
    """Run all structural checks and return combined issues."""
    issues = []
    issues.extend(check_heading_structure(html))
    issues.extend(check_landmarks(html))
    issues.extend(check_form_labels(html))
    return issues
