"""
Tool definitions and execution for the accessibility agent.
Each tool maps to a Playwright browser action that Claude can invoke.
"""

import base64
import json

from playwright.sync_api import Page


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic tool-use schema)
# ---------------------------------------------------------------------------

PRESS_KEY = {
    "name": "press_key",
    "description": (
        "Press a keyboard key on the page. Use this to simulate real keyboard "
        "navigation — Tab to move forward, Shift+Tab to move backward, Enter "
        "to activate, Escape to dismiss, Space to toggle, Arrow keys for widgets."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": (
                    "Key to press. Supported: Tab, Shift+Tab, Enter, Escape, "
                    "Space, ArrowDown, ArrowUp, ArrowLeft, ArrowRight"
                ),
            }
        },
        "required": ["key"],
    },
}

GET_FOCUS_STATE = {
    "name": "get_focus_state",
    "description": (
        "Get full details about the currently focused element — tag, role, "
        "accessible name, text content, outline/box-shadow visibility, "
        "bounding box, and ARIA attributes. Call this after press_key to "
        "inspect where focus landed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

GET_FOCUSABLE_ELEMENTS = {
    "name": "get_focusable_elements",
    "description": (
        "List all focusable elements on the page in DOM order. Returns tag, "
        "role, accessible name, tabindex, and whether it appears to be a "
        "skip link. Use this to understand the tab order before navigating."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

GET_ACCESSIBILITY_TREE = {
    "name": "get_accessibility_tree",
    "description": (
        "Get the browser's accessibility tree for the page. This is the "
        "structure a screen reader would present — roles, names, states, "
        "and hierarchy. Use this to evaluate whether the page makes sense "
        "when consumed non-visually."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "root_selector": {
                "type": "string",
                "description": (
                    "Optional CSS selector to scope the tree to a subtree. "
                    "Omit for the full page tree."
                ),
            }
        },
    },
}

GET_LANDMARKS = {
    "name": "get_landmarks",
    "description": (
        "Get all ARIA landmark regions on the page (banner, navigation, "
        "main, complementary, contentinfo, search, form, region). Returns "
        "role, label, and child heading summary for each."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

GET_LIVE_REGIONS = {
    "name": "get_live_regions",
    "description": (
        "Find all ARIA live regions (aria-live, role=alert, role=status, "
        "role=log, role=marquee, role=timer) and their current content. "
        "Use this to check if dynamic updates are announced."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

GET_ELEMENT_DETAILS = {
    "name": "get_element_details",
    "description": (
        "Get detailed accessibility properties for a specific element — "
        "computed role, name, description, states, and all ARIA attributes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "CSS selector for the element to inspect.",
            }
        },
        "required": ["selector"],
    },
}

TAKE_SCREENSHOT = {
    "name": "take_screenshot",
    "description": (
        "Capture a full-page screenshot. Returns the image for visual "
        "analysis of layout, spacing, colour usage, visual hierarchy, "
        "and cognitive load assessment."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "full_page": {
                "type": "boolean",
                "description": "Capture full scrollable page (true) or just viewport (false). Default: false.",
            }
        },
    },
}

GET_PAGE_METRICS = {
    "name": "get_page_metrics",
    "description": (
        "Get quantitative content metrics: word count, link count, "
        "form field count, heading count, image count, average paragraph "
        "length, reading level estimate, and colour palette."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

GET_VISIBLE_TEXT = {
    "name": "get_visible_text",
    "description": (
        "Get all visible text content from the page in reading order. "
        "Useful for assessing plain language, reading flow, and content clarity."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "max_length": {
                "type": "integer",
                "description": "Max characters to return. Default: 8000.",
            }
        },
    },
}

NAVIGATE_TO = {
    "name": "navigate_to",
    "description": (
        "Navigate the browser to a specific URL. Use this to follow links "
        "and test multi-page flows. Only navigate to pages within the same "
        "site origin."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to navigate to.",
            }
        },
        "required": ["url"],
    },
}

CLICK_ELEMENT = {
    "name": "click_element",
    "description": (
        "Click an element on the page by CSS selector. Use this to interact "
        "with links, buttons, dropdowns, or other interactive elements "
        "during multi-page journey testing."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "CSS selector for the element to click.",
            }
        },
        "required": ["selector"],
    },
}

GET_LINKS = {
    "name": "get_links",
    "description": (
        "Get all links on the current page — href, text, whether internal "
        "or external, and their location in the page structure."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

GET_PAGE_URL = {
    "name": "get_page_url",
    "description": "Get the current page URL.",
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

# Grouped by persona
KEYBOARD_TOOLS = [PRESS_KEY, GET_FOCUS_STATE, GET_FOCUSABLE_ELEMENTS]
SCREEN_READER_TOOLS = [GET_ACCESSIBILITY_TREE, GET_LANDMARKS, GET_LIVE_REGIONS, GET_ELEMENT_DETAILS]
COGNITIVE_TOOLS = [TAKE_SCREENSHOT, GET_PAGE_METRICS, GET_VISIBLE_TEXT]
JOURNEY_TOOLS = [NAVIGATE_TO, CLICK_ELEMENT, GET_LINKS, GET_PAGE_URL]
ALL_TOOLS = KEYBOARD_TOOLS + SCREEN_READER_TOOLS + COGNITIVE_TOOLS + JOURNEY_TOOLS


# ---------------------------------------------------------------------------
# Tool execution — maps tool names to Playwright actions
# ---------------------------------------------------------------------------

def execute_tool(tool_name: str, tool_input: dict, page: Page) -> str | dict:
    """Dispatch a tool call to its Playwright implementation. Returns result."""
    handler = _HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return handler(page, tool_input)
    except Exception as e:
        return {"error": f"Tool {tool_name} failed: {e}"}


# -- Keyboard tools --

def _press_key(page: Page, inp: dict) -> dict:
    key = inp.get("key", "Tab")
    # Map friendly names to Playwright key names
    key_map = {
        "Shift+Tab": "Shift+Tab",
        "ArrowDown": "ArrowDown",
        "ArrowUp": "ArrowUp",
        "ArrowLeft": "ArrowLeft",
        "ArrowRight": "ArrowRight",
    }
    pw_key = key_map.get(key, key)
    page.keyboard.press(pw_key)
    page.wait_for_timeout(150)  # Brief pause for focus to settle
    return {"pressed": key, "status": "ok"}


def _get_focus_state(page: Page, _inp: dict) -> dict:
    return page.evaluate("""
    () => {
        const el = document.activeElement;
        if (!el || el === document.body || el === document.documentElement)
            return {focused: false, element: "body"};

        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        const outlineStyle = style.outlineStyle;
        const outlineWidth = parseFloat(style.outlineWidth);
        const outlineColor = style.outlineColor;
        const boxShadow = style.boxShadow;

        // Compute accessible name
        const ariaLabel = el.getAttribute('aria-label') || '';
        const ariaLabelledBy = el.getAttribute('aria-labelledby');
        let accName = ariaLabel;
        if (ariaLabelledBy) {
            const refEl = document.getElementById(ariaLabelledBy);
            if (refEl) accName = refEl.textContent.trim();
        }
        if (!accName) {
            const label = el.closest('label') || document.querySelector(`label[for="${el.id}"]`);
            if (label) accName = label.textContent.trim();
        }
        if (!accName) accName = el.textContent ? el.textContent.trim().substring(0, 80) : '';

        return {
            focused: true,
            tag: el.tagName.toLowerCase(),
            role: el.getAttribute('role') || el.tagName.toLowerCase(),
            type: el.getAttribute('type') || '',
            id: el.id || '',
            className: (typeof el.className === 'string') ? el.className.substring(0, 100) : '',
            accessibleName: accName.substring(0, 120),
            text: (el.textContent || '').trim().substring(0, 80),
            href: el.getAttribute('href') || '',
            tabindex: el.getAttribute('tabindex'),
            ariaExpanded: el.getAttribute('aria-expanded'),
            ariaHaspopup: el.getAttribute('aria-haspopup'),
            ariaHidden: el.getAttribute('aria-hidden'),
            disabled: el.disabled || false,
            focus_visible: {
                has_outline: outlineStyle !== 'none' && outlineWidth > 0,
                outline_style: outlineStyle,
                outline_width: outlineWidth + 'px',
                outline_color: outlineColor,
                has_box_shadow: boxShadow !== 'none',
                box_shadow: boxShadow !== 'none' ? boxShadow.substring(0, 100) : 'none',
            },
            bounding_box: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                width: Math.round(rect.width),
                height: Math.round(rect.height),
            },
        };
    }
    """)


def _get_focusable_elements(page: Page, _inp: dict) -> dict:
    elements = page.evaluate("""
    () => {
        const selector = 'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"]), details, summary';
        const els = [...document.querySelectorAll(selector)].filter(el => {
            const style = window.getComputedStyle(el);
            return style.display !== 'none' && style.visibility !== 'hidden' && !el.disabled;
        });
        return els.map((el, index) => {
            const ariaLabel = el.getAttribute('aria-label') || '';
            const text = (el.textContent || '').trim().substring(0, 60);
            const href = el.getAttribute('href') || '';
            const isSkipLink = (
                (text.toLowerCase().includes('skip') && href.startsWith('#')) ||
                (ariaLabel.toLowerCase().includes('skip') && href.startsWith('#'))
            );
            return {
                index: index,
                tag: el.tagName.toLowerCase(),
                role: el.getAttribute('role') || '',
                type: el.getAttribute('type') || '',
                accessibleName: ariaLabel || text,
                href: href,
                tabindex: el.getAttribute('tabindex'),
                isSkipLink: isSkipLink,
                ariaExpanded: el.getAttribute('aria-expanded'),
                ariaHaspopup: el.getAttribute('aria-haspopup'),
            };
        });
    }
    """)
    return {"count": len(elements), "elements": elements}


# -- Screen reader tools --

def _get_accessibility_tree(page: Page, inp: dict) -> dict:
    root_selector = inp.get("root_selector")

    snapshot = page.accessibility.snapshot(interesting_only=True)
    if not snapshot:
        return {"error": "Could not retrieve accessibility tree"}

    def _trim_tree(node, depth=0, max_depth=6):
        """Trim tree to manageable size for Claude context."""
        if depth > max_depth:
            return None
        trimmed = {
            "role": node.get("role", ""),
            "name": (node.get("name") or "")[:100],
        }
        # Include important states
        for key in ("checked", "disabled", "expanded", "level",
                     "pressed", "selected", "required", "invalid"):
            if key in node:
                trimmed[key] = node[key]

        children = node.get("children", [])
        if children:
            trimmed_children = []
            for child in children:
                tc = _trim_tree(child, depth + 1, max_depth)
                if tc:
                    trimmed_children.append(tc)
            if trimmed_children:
                trimmed["children"] = trimmed_children
        return trimmed

    tree = _trim_tree(snapshot)

    # If root_selector specified, try to scope
    if root_selector:
        try:
            el = page.query_selector(root_selector)
            if el:
                scoped = page.accessibility.snapshot(interesting_only=True, root=el)
                if scoped:
                    tree = _trim_tree(scoped)
        except Exception:
            pass  # Fall back to full tree

    return {"tree": tree}


def _get_landmarks(page: Page, _inp: dict) -> dict:
    return page.evaluate("""
    () => {
        const landmarkRoles = ['banner', 'navigation', 'main', 'complementary',
                               'contentinfo', 'search', 'form', 'region'];
        const roleSelectors = landmarkRoles.map(r => `[role="${r}"]`).join(', ');
        const htmlLandmarks = 'header, nav, main, aside, footer, form[aria-label], form[aria-labelledby], section[aria-label], section[aria-labelledby]';
        const els = [...document.querySelectorAll(roleSelectors + ', ' + htmlLandmarks)];

        const tagToRole = {header: 'banner', nav: 'navigation', main: 'main',
                           aside: 'complementary', footer: 'contentinfo',
                           form: 'form', section: 'region'};

        return els.map(el => {
            const role = el.getAttribute('role') || tagToRole[el.tagName.toLowerCase()] || 'unknown';
            const label = el.getAttribute('aria-label') ||
                          (el.getAttribute('aria-labelledby') ?
                           document.getElementById(el.getAttribute('aria-labelledby'))?.textContent?.trim() : '') || '';
            // Get first heading inside
            const heading = el.querySelector('h1, h2, h3, h4, h5, h6');
            const headingText = heading ? heading.textContent.trim().substring(0, 60) : '';
            return {role, label: label.substring(0, 80), firstHeading: headingText};
        });
    }
    """)


def _get_live_regions(page: Page, _inp: dict) -> dict:
    return page.evaluate("""
    () => {
        const liveEls = document.querySelectorAll(
            '[aria-live], [role="alert"], [role="status"], [role="log"], [role="marquee"], [role="timer"]'
        );
        return [...liveEls].map(el => ({
            role: el.getAttribute('role') || '',
            ariaLive: el.getAttribute('aria-live') || '',
            ariaAtomic: el.getAttribute('aria-atomic') || '',
            ariaRelevant: el.getAttribute('aria-relevant') || '',
            content: (el.textContent || '').trim().substring(0, 200),
            selector: el.id ? '#' + el.id : el.tagName.toLowerCase() + (el.className ? '.' + el.className.split(' ')[0] : ''),
        }));
    }
    """)


def _get_element_details(page: Page, inp: dict) -> dict:
    selector = inp.get("selector", "")
    if not selector:
        return {"error": "selector is required"}

    result = page.evaluate("""
    (selector) => {
        const el = document.querySelector(selector);
        if (!el) return {error: 'Element not found: ' + selector};

        const attrs = {};
        for (const attr of el.attributes) {
            if (attr.name.startsWith('aria-') || attr.name === 'role' ||
                attr.name === 'tabindex' || attr.name === 'title') {
                attrs[attr.name] = attr.value;
            }
        }

        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();

        return {
            tag: el.tagName.toLowerCase(),
            role: el.getAttribute('role') || '',
            computedRole: el.computedRole || '',
            accessibleName: el.getAttribute('aria-label') || el.textContent?.trim()?.substring(0, 100) || '',
            accessibleDescription: el.getAttribute('aria-describedby') ?
                document.getElementById(el.getAttribute('aria-describedby'))?.textContent?.trim()?.substring(0, 100) : '',
            ariaAttributes: attrs,
            isVisible: style.display !== 'none' && style.visibility !== 'hidden',
            bounding_box: {x: Math.round(rect.x), y: Math.round(rect.y),
                           width: Math.round(rect.width), height: Math.round(rect.height)},
        };
    }
    """, selector)
    return result


# -- Cognitive tools --

def _take_screenshot(page: Page, inp: dict) -> dict:
    full_page = inp.get("full_page", False)
    screenshot_bytes = page.screenshot(full_page=full_page, type="png")
    b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
    return {"_screenshot_base64": b64}


def _get_page_metrics(page: Page, _inp: dict) -> dict:
    return page.evaluate("""
    () => {
        const body = document.body;
        const text = body.innerText || '';
        const words = text.split(/\\s+/).filter(w => w.length > 0);
        const links = document.querySelectorAll('a[href]');
        const inputs = document.querySelectorAll('input, select, textarea');
        const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
        const images = document.querySelectorAll('img');
        const buttons = document.querySelectorAll('button, [role="button"], input[type="submit"]');
        const paragraphs = document.querySelectorAll('p');

        // Average paragraph length
        let totalParaWords = 0;
        paragraphs.forEach(p => {
            totalParaWords += (p.textContent || '').split(/\\s+/).filter(w => w.length > 0).length;
        });
        const avgParaLength = paragraphs.length > 0 ? Math.round(totalParaWords / paragraphs.length) : 0;

        // Unique colours used on text elements
        const colours = new Set();
        const bgColours = new Set();
        const textEls = document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, a, span, li, td, th, label, button');
        textEls.forEach(el => {
            const style = window.getComputedStyle(el);
            colours.add(style.color);
            bgColours.add(style.backgroundColor);
        });

        return {
            word_count: words.length,
            link_count: links.length,
            form_field_count: inputs.length,
            button_count: buttons.length,
            heading_count: headings.length,
            image_count: images.length,
            paragraph_count: paragraphs.length,
            avg_paragraph_words: avgParaLength,
            unique_text_colours: colours.size,
            unique_bg_colours: bgColours.size,
            page_height_px: document.documentElement.scrollHeight,
            viewport_height_px: window.innerHeight,
            scrollable_pages: Math.round(document.documentElement.scrollHeight / window.innerHeight * 10) / 10,
        };
    }
    """)


def _get_visible_text(page: Page, inp: dict) -> dict:
    max_length = inp.get("max_length", 8000)
    text = page.evaluate("""
    (maxLen) => {
        const body = document.body;
        if (!body) return '';
        return (body.innerText || '').substring(0, maxLen);
    }
    """, max_length)
    return {"text": text, "length": len(text)}


# -- Journey tools --

def _navigate_to(page: Page, inp: dict) -> dict:
    url = inp.get("url", "")
    if not url:
        return {"error": "url is required"}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        return {"navigated_to": page.url, "title": page.title()}
    except Exception as e:
        return {"error": f"Navigation failed: {e}"}


def _click_element(page: Page, inp: dict) -> dict:
    selector = inp.get("selector", "")
    if not selector:
        return {"error": "selector is required"}
    try:
        page.locator(selector).first.click(timeout=5000)
        page.wait_for_timeout(1000)
        return {"clicked": selector, "current_url": page.url, "title": page.title()}
    except Exception as e:
        return {"error": f"Click failed: {e}"}


def _get_links(page: Page, _inp: dict) -> dict:
    current_origin = page.evaluate("() => window.location.origin")
    links = page.evaluate("""
    (origin) => {
        return [...document.querySelectorAll('a[href]')].map(a => {
            const href = a.href;
            const text = (a.textContent || '').trim().substring(0, 60);
            const ariaLabel = a.getAttribute('aria-label') || '';
            const isInternal = href.startsWith(origin) || href.startsWith('/');
            const inNav = !!a.closest('nav, [role="navigation"]');
            const inFooter = !!a.closest('footer, [role="contentinfo"]');
            const inMain = !!a.closest('main, [role="main"]');
            return {href, text: ariaLabel || text, isInternal, inNav, inFooter, inMain};
        }).filter(l => l.href && !l.href.startsWith('javascript:'));
    }
    """, current_origin)
    return {"count": len(links), "links": links[:100]}  # Cap at 100


def _get_page_url(page: Page, _inp: dict) -> dict:
    return {"url": page.url, "title": page.title()}


# Handler registry
_HANDLERS = {
    "press_key": _press_key,
    "get_focus_state": _get_focus_state,
    "get_focusable_elements": _get_focusable_elements,
    "get_accessibility_tree": _get_accessibility_tree,
    "get_landmarks": _get_landmarks,
    "get_live_regions": _get_live_regions,
    "get_element_details": _get_element_details,
    "take_screenshot": _take_screenshot,
    "get_page_metrics": _get_page_metrics,
    "get_visible_text": _get_visible_text,
    "navigate_to": _navigate_to,
    "click_element": _click_element,
    "get_links": _get_links,
    "get_page_url": _get_page_url,
}
