"""
Resolve human-friendly element descriptions and page locations from CSS selectors.
Uses Playwright to query the live DOM for bounding boxes and context.
"""

import re

from playwright.sync_api import Page

from accessibility_sweep.models import Issue

# Maps tag names to human-readable labels
TAG_LABELS = {
    "a": "Link",
    "button": "Button",
    "input": "Input field",
    "select": "Dropdown",
    "textarea": "Text area",
    "img": "Image",
    "nav": "Navigation",
    "header": "Header",
    "footer": "Footer",
    "main": "Main content",
    "aside": "Sidebar",
    "form": "Form",
    "table": "Table",
    "ul": "List",
    "ol": "Numbered list",
    "li": "List item",
    "h1": "Main heading",
    "h2": "Section heading",
    "h3": "Sub-heading",
    "h4": "Sub-heading",
    "h5": "Sub-heading",
    "h6": "Sub-heading",
    "p": "Paragraph",
    "span": "Text",
    "div": "Section",
    "label": "Label",
    "video": "Video",
    "audio": "Audio",
    "iframe": "Embedded content",
    "section": "Section",
    "article": "Article",
    "dialog": "Dialog",
    "td": "Table cell",
    "th": "Table header",
}

INPUT_TYPE_LABELS = {
    "text": "Text input",
    "email": "Email input",
    "password": "Password input",
    "search": "Search input",
    "tel": "Phone input",
    "url": "URL input",
    "number": "Number input",
    "checkbox": "Checkbox",
    "radio": "Radio button",
    "file": "File upload",
    "date": "Date picker",
    "range": "Slider",
    "color": "Colour picker",
}


def _describe_selector(selector: str) -> str:
    """Convert a CSS selector into a human-readable description."""
    if not selector or selector == "document":
        return "Entire page"

    # Extract tag name from selector like "div.classname", "a#id", "input[name='x']"
    tag_match = re.match(r'^([a-z][a-z0-9]*)', selector, re.IGNORECASE)
    tag = tag_match.group(1).lower() if tag_match else ""

    # Extract id
    id_match = re.search(r'#([a-zA-Z0-9_-]+)', selector)
    el_id = id_match.group(1) if id_match else ""

    # Extract first class
    class_match = re.search(r'\.([a-zA-Z0-9_-]+)', selector)
    el_class = class_match.group(1) if class_match else ""

    # Extract input type if present
    type_match = re.search(r"\[type=['\"]?([a-z]+)['\"]?\]", selector)
    input_type = type_match.group(1) if type_match else ""

    # Build friendly name
    if tag == "input" and input_type:
        label = INPUT_TYPE_LABELS.get(input_type, f"{input_type.title()} input")
    else:
        label = TAG_LABELS.get(tag, tag.upper() if tag else "Element")

    # Add context from id or class (humanised)
    context_hint = ""
    raw_hint = el_id or el_class
    if raw_hint:
        # Convert kebab-case/camelCase/snake_case to words
        words = re.sub(r'[-_]', ' ', raw_hint)
        words = re.sub(r'([a-z])([A-Z])', r'\1 \2', words)
        words = words.strip().lower()
        # Filter out generic noise
        noise = {"js", "css", "wp", "el", "wrapper", "container", "inner", "outer", "block", "component"}
        meaningful = [w for w in words.split() if w not in noise and len(w) > 1]
        if meaningful:
            context_hint = " ".join(meaningful[:3])

    if context_hint:
        return f"{label} ({context_hint})"
    return label


def _page_region(x: float, y: float, page_width: float, page_height: float) -> str:
    """Map absolute coordinates to a page region label."""
    # Vertical position
    if y < page_height * 0.15:
        v = "Top"
    elif y < page_height * 0.5:
        v = "Upper"
    elif y < page_height * 0.85:
        v = "Lower"
    else:
        v = "Bottom"

    # Horizontal position
    if x < page_width * 0.33:
        h = "left"
    elif x < page_width * 0.66:
        h = "centre"
    else:
        h = "right"

    return f"{v} {h} of page"


def enrich_issues_with_context(page: Page, issues: list[Issue]) -> None:
    """
    For each issue, resolve a human-friendly description and page location
    by querying the live Playwright page for bounding boxes.
    Modifies issues in place.
    """
    viewport = page.viewport_size or {"width": 1280, "height": 720}
    # Get full page height for region calculation
    full_height = page.evaluate("() => document.documentElement.scrollHeight") or viewport["height"]
    page_width = viewport["width"]

    for issue in issues:
        # Always set a friendly description
        if not issue.element_description:
            issue.element_description = _describe_selector(issue.element)

        # Skip non-selector elements
        if not issue.element or issue.element == "document":
            continue

        # Try to get bounding box from the live page
        if not issue.bounding_box:
            try:
                loc = page.locator(issue.element).first
                bbox = loc.bounding_box(timeout=2000)
                if bbox:
                    # Store normalised percentages for minimap rendering
                    cx = bbox["x"] + bbox["width"] / 2
                    cy = bbox["y"] + bbox["height"] / 2
                    issue.bounding_box = {
                        "x": round(bbox["x"]),
                        "y": round(bbox["y"]),
                        "width": round(bbox["width"]),
                        "height": round(bbox["height"]),
                        "pct_x": round(min(cx / page_width * 100, 95), 1),
                        "pct_y": round(min(cy / full_height * 100, 95), 1),
                    }
                    # Also set visual_location if not already set
                    if not issue.visual_location:
                        cx = bbox["x"] + bbox["width"] / 2
                        cy = bbox["y"] + bbox["height"] / 2
                        issue.visual_location = _page_region(cx, cy, page_width, full_height)
            except Exception:
                pass  # Element may not be queryable
