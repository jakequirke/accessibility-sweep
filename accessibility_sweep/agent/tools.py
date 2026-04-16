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
                    "Space, ArrowDown, ArrowUp, ArrowLeft, ArrowRight, "
                    "Home, End, PageUp, PageDown"
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

GET_HEADINGS = {
    "name": "get_headings",
    "description": (
        "Get an ordered list of all headings on the page with their level, "
        "text content, and nesting context. Use this to evaluate whether "
        "the heading hierarchy creates a logical, navigable document outline."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

GET_FORM_FIELDS = {
    "name": "get_form_fields",
    "description": (
        "Get all form inputs on the page with their labels, descriptions, "
        "required state, error state, autocomplete attribute, type, and "
        "whether they have a programmatically associated label. Use this "
        "to evaluate form accessibility comprehensively."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

GET_ERROR_MESSAGES = {
    "name": "get_error_messages",
    "description": (
        "Find all visible error messages on the page — form validation "
        "errors, alert banners, and inline error text. Returns each error's "
        "text, the field it relates to (if any), and whether it is "
        "programmatically associated via aria-describedby or aria-errormessage."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

GET_PAGE_TEXT = {
    "name": "get_page_text",
    "description": (
        "Get the full visible text content in reading order with structural "
        "markers — headings are prefixed with their level (e.g. [H1], [H2]), "
        "landmarks are marked with [NAV], [MAIN], [FOOTER], etc. This gives "
        "a screen-reader-like view of the page content flow."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "max_length": {
                "type": "integer",
                "description": "Max characters to return. Default: 10000.",
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

# Grouped by persona — each persona gets the tools it needs to evaluate
# the page from its specific perspective.
KEYBOARD_TOOLS = [
    PRESS_KEY, GET_FOCUS_STATE, GET_FOCUSABLE_ELEMENTS,
    GET_ACCESSIBILITY_TREE, GET_HEADINGS,
]
SCREEN_READER_TOOLS = [
    GET_ACCESSIBILITY_TREE, GET_PAGE_TEXT, GET_ELEMENT_DETAILS,
    GET_LIVE_REGIONS, GET_HEADINGS, GET_LANDMARKS, GET_FORM_FIELDS,
    PRESS_KEY,
]
COGNITIVE_TOOLS = [
    TAKE_SCREENSHOT, GET_PAGE_METRICS, GET_PAGE_TEXT,
    GET_FORM_FIELDS, GET_HEADINGS, GET_ERROR_MESSAGES,
]
JOURNEY_TOOLS = [NAVIGATE_TO, CLICK_ELEMENT, GET_LINKS, GET_PAGE_URL]
ALL_TOOLS = list({t["name"]: t for t in (
    KEYBOARD_TOOLS + SCREEN_READER_TOOLS + COGNITIVE_TOOLS + JOURNEY_TOOLS
)}.values())


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
    valid_keys = {
        "Tab", "Shift+Tab", "Enter", "Space", "Escape",
        "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
        "Home", "End", "PageUp", "PageDown",
    }
    if key not in valid_keys:
        return {"error": f"Invalid key: {key}. Valid keys: {', '.join(sorted(valid_keys))}"}
    page.keyboard.press(key)
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

        // Check if element is obscured by sticky/fixed positioned elements
        // (WCAG 2.4.11 Focus Not Obscured)
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        let isObscured = false;
        let obscuredBy = '';
        if (rect.width > 0 && rect.height > 0) {
            const topElement = document.elementFromPoint(centerX, centerY);
            if (topElement && topElement !== el && !el.contains(topElement) && !topElement.contains(el)) {
                const topStyle = window.getComputedStyle(topElement);
                const pos = topStyle.position;
                if (pos === 'fixed' || pos === 'sticky') {
                    isObscured = true;
                    obscuredBy = topElement.tagName.toLowerCase()
                        + (topElement.id ? '#' + topElement.id : '')
                        + (topElement.className ? '.' + String(topElement.className).split(' ')[0] : '')
                        + ' (position: ' + pos + ')';
                }
            }
        }

        const inViewport = rect.top >= 0 && rect.top <= window.innerHeight
            && rect.left >= 0 && rect.left <= window.innerWidth;

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
            is_obscured: isObscured,
            obscured_by: obscuredBy,
            in_viewport: inViewport,
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


# -- Shared inspection tools --

def _get_headings(page: Page, _inp: dict) -> dict:
    headings = page.evaluate("""
    () => {
        const headings = [...document.querySelectorAll('h1, h2, h3, h4, h5, h6')];
        let previousLevel = 0;
        return headings.map((h, index) => {
            const level = parseInt(h.tagName[1]);
            const skipped = level > previousLevel + 1 && previousLevel > 0;
            const result = {
                index: index,
                level: level,
                tag: h.tagName.toLowerCase(),
                text: h.textContent.trim().substring(0, 120),
                id: h.id || '',
                skippedLevel: skipped,
                previousLevel: previousLevel,
                inLandmark: h.closest('main, nav, aside, header, footer, [role="main"], [role="navigation"], [role="complementary"], [role="banner"], [role="contentinfo"]')?.tagName?.toLowerCase() || '',
            };
            previousLevel = level;
            return result;
        });
    }
    """)
    h1_count = sum(1 for h in headings if h["level"] == 1)
    return {
        "count": len(headings),
        "h1_count": h1_count,
        "headings": headings,
    }


def _get_form_fields(page: Page, _inp: dict) -> dict:
    fields = page.evaluate("""
    () => {
        const inputs = [...document.querySelectorAll('input, select, textarea')];
        return inputs.filter(el => {
            const type = (el.getAttribute('type') || 'text').toLowerCase();
            return type !== 'hidden';
        }).map(el => {
            const type = (el.getAttribute('type') || 'text').toLowerCase();
            const id = el.id || '';
            const name = el.getAttribute('name') || '';

            // Check for associated label
            let labelText = '';
            let hasLabel = false;
            if (id) {
                const label = document.querySelector(`label[for="${id}"]`);
                if (label) { labelText = label.textContent.trim(); hasLabel = true; }
            }
            if (!hasLabel) {
                const parentLabel = el.closest('label');
                if (parentLabel) { labelText = parentLabel.textContent.trim(); hasLabel = true; }
            }
            const ariaLabel = el.getAttribute('aria-label') || '';
            const ariaLabelledBy = el.getAttribute('aria-labelledby') || '';
            if (ariaLabel) hasLabel = true;
            if (ariaLabelledBy) {
                const ref = document.getElementById(ariaLabelledBy);
                if (ref) { labelText = ref.textContent.trim(); hasLabel = true; }
            }

            // Check for description
            const describedBy = el.getAttribute('aria-describedby') || '';
            let description = '';
            if (describedBy) {
                const desc = document.getElementById(describedBy);
                if (desc) description = desc.textContent.trim();
            }

            // Error state
            const isInvalid = el.getAttribute('aria-invalid') === 'true'
                || el.classList.contains('error')
                || el.classList.contains('invalid');
            const errorMsg = el.getAttribute('aria-errormessage') || '';
            let errorText = '';
            if (errorMsg) {
                const errEl = document.getElementById(errorMsg);
                if (errEl) errorText = errEl.textContent.trim();
            }

            return {
                tag: el.tagName.toLowerCase(),
                type: type,
                id: id,
                name: name,
                hasLabel: hasLabel,
                labelText: (ariaLabel || labelText).substring(0, 80),
                description: description.substring(0, 100),
                required: el.hasAttribute('required') || el.getAttribute('aria-required') === 'true',
                disabled: el.disabled || el.getAttribute('aria-disabled') === 'true',
                autocomplete: el.getAttribute('autocomplete') || '',
                isInvalid: isInvalid,
                errorText: errorText.substring(0, 100),
                placeholder: el.getAttribute('placeholder') || '',
                value: type === 'password' ? '(hidden)' : (el.value || '').substring(0, 50),
            };
        });
    }
    """)
    unlabelled = sum(1 for f in fields if not f["hasLabel"])
    return {
        "count": len(fields),
        "unlabelled_count": unlabelled,
        "fields": fields,
    }


def _get_error_messages(page: Page, _inp: dict) -> dict:
    errors = page.evaluate("""
    () => {
        const results = [];

        // ARIA error references
        const invalidFields = document.querySelectorAll('[aria-invalid="true"]');
        invalidFields.forEach(field => {
            const errMsgId = field.getAttribute('aria-errormessage');
            const describedBy = field.getAttribute('aria-describedby');
            let errorText = '';
            if (errMsgId) {
                const el = document.getElementById(errMsgId);
                if (el) errorText = el.textContent.trim();
            }
            if (!errorText && describedBy) {
                const el = document.getElementById(describedBy);
                if (el) errorText = el.textContent.trim();
            }
            results.push({
                type: 'field_error',
                fieldSelector: field.id ? '#' + field.id : field.tagName.toLowerCase() + '[name="' + (field.getAttribute('name') || '') + '"]',
                fieldLabel: field.getAttribute('aria-label') || '',
                errorText: errorText.substring(0, 200),
                programmaticallyAssociated: !!(errMsgId || describedBy),
            });
        });

        // Alert roles
        const alerts = document.querySelectorAll('[role="alert"], .alert, .error-message, .error-summary, .form-error, .field-error, .validation-error');
        alerts.forEach(el => {
            const text = el.textContent.trim();
            if (text && !results.some(r => r.errorText === text)) {
                results.push({
                    type: el.getAttribute('role') === 'alert' ? 'alert' : 'error_message',
                    fieldSelector: '',
                    fieldLabel: '',
                    errorText: text.substring(0, 200),
                    programmaticallyAssociated: el.getAttribute('role') === 'alert',
                });
            }
        });

        return results;
    }
    """)
    return {"count": len(errors), "errors": errors}


def _get_page_text(page: Page, inp: dict) -> dict:
    max_length = inp.get("max_length", 10000)
    text = page.evaluate("""
    (maxLen) => {
        const landmarkMap = {
            'HEADER': 'BANNER', 'NAV': 'NAV', 'MAIN': 'MAIN',
            'ASIDE': 'COMPLEMENTARY', 'FOOTER': 'CONTENTINFO',
            'SECTION': 'REGION', 'FORM': 'FORM',
        };
        const roleMap = {
            'banner': 'BANNER', 'navigation': 'NAV', 'main': 'MAIN',
            'complementary': 'COMPLEMENTARY', 'contentinfo': 'CONTENTINFO',
            'search': 'SEARCH', 'form': 'FORM', 'region': 'REGION',
        };

        function walk(node, depth) {
            if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent.trim();
                return text ? text + ' ' : '';
            }
            if (node.nodeType !== Node.ELEMENT_NODE) return '';

            const tag = node.tagName;
            const style = window.getComputedStyle(node);
            if (style.display === 'none' || style.visibility === 'hidden') return '';
            if (node.getAttribute('aria-hidden') === 'true') return '';

            let result = '';

            // Landmark markers
            const role = node.getAttribute('role');
            const landmark = roleMap[role] || landmarkMap[tag] || '';
            if (landmark) result += '\\n[' + landmark + ']\\n';

            // Heading markers
            if (/^H[1-6]$/.test(tag)) {
                result += '\\n[' + tag + '] ' + node.textContent.trim() + '\\n';
                return result;
            }

            // List markers
            if (tag === 'LI') result += '• ';
            if (tag === 'BR') result += '\\n';

            for (const child of node.childNodes) {
                result += walk(child, depth + 1);
            }

            // Block-level elements get line breaks
            if (['P', 'DIV', 'BLOCKQUOTE', 'UL', 'OL', 'TABLE', 'TR',
                 'FIGCAPTION', 'FIGURE', 'DT', 'DD'].includes(tag)) {
                result += '\\n';
            }

            if (landmark) result += '[/' + landmark + ']\\n';

            return result;
        }

        let text = walk(document.body, 0);
        // Clean up excessive whitespace
        text = text.replace(/\\n{3,}/g, '\\n\\n').trim();
        return text.substring(0, maxLen);
    }
    """, max_length)
    return {"text": text, "length": len(text)}


# -- Cognitive tools --

def _take_screenshot(page: Page, inp: dict) -> dict:
    full_page = inp.get("full_page", False)
    screenshot_bytes = page.screenshot(full_page=full_page, type="png")
    b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
    return {"_screenshot_base64": b64}


def _get_page_metrics(page: Page, _inp: dict) -> dict:
    metrics = page.evaluate("""
    () => {
        const body = document.body;
        const text = body.innerText || '';
        const words = text.split(/\\s+/).filter(w => w.length > 0);
        const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 0);
        const links = document.querySelectorAll('a[href]');
        const inputs = document.querySelectorAll('input, select, textarea');
        const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
        const images = document.querySelectorAll('img');
        const buttons = document.querySelectorAll('button, [role="button"], input[type="submit"]');
        const paragraphs = document.querySelectorAll('p');
        const videos = document.querySelectorAll('video, iframe[src*="youtube"], iframe[src*="vimeo"]');
        const animations = document.querySelectorAll(
            '[class*="animate"], [class*="carousel"], [class*="slider"], [class*="marquee"], [class*="scroll"]'
        );
        const autoplay = document.querySelectorAll('video[autoplay], audio[autoplay]');
        const ctas = document.querySelectorAll(
            'a.btn, a.button, a[class*="cta"], button:not([type="reset"]):not([type="button"]), '
            + '[role="button"], input[type="submit"]'
        );

        // Average paragraph length
        let totalParaWords = 0;
        paragraphs.forEach(p => {
            totalParaWords += (p.textContent || '').split(/\\s+/).filter(w => w.length > 0).length;
        });
        const avgParaLength = paragraphs.length > 0 ? Math.round(totalParaWords / paragraphs.length) : 0;

        // Abbreviations (2+ uppercase letters)
        const abbreviations = text.match(/\\b[A-Z]{2,}\\b/g) || [];
        const uniqueAbbreviations = [...new Set(abbreviations)];

        // Syllable count estimation for Flesch-Kincaid
        function countSyllables(word) {
            word = word.toLowerCase().replace(/[^a-z]/g, '');
            if (word.length <= 3) return 1;
            word = word.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, '');
            word = word.replace(/^y/, '');
            const vowelGroups = word.match(/[aeiouy]{1,2}/g);
            return vowelGroups ? vowelGroups.length : 1;
        }
        let totalSyllables = 0;
        words.forEach(w => { totalSyllables += countSyllables(w); });

        // Flesch-Kincaid Grade Level
        let fleschKincaidGrade = 0;
        if (sentences.length > 0 && words.length > 0) {
            fleschKincaidGrade = Math.round(
                (0.39 * (words.length / sentences.length) +
                 11.8 * (totalSyllables / words.length) - 15.59) * 10
            ) / 10;
        }

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
            unique_word_count: [...new Set(words.map(w => w.toLowerCase()))].length,
            sentence_count: sentences.length,
            average_sentence_length: sentences.length > 0 ? Math.round(words.length / sentences.length) : 0,
            flesch_kincaid_grade: fleschKincaidGrade,
            link_count: links.length,
            form_field_count: inputs.length,
            button_count: buttons.length,
            heading_count: headings.length,
            image_count: images.length,
            video_count: videos.length,
            paragraph_count: paragraphs.length,
            avg_paragraph_words: avgParaLength,
            has_animations: animations.length > 0,
            has_autoplay: autoplay.length > 0,
            call_to_action_count: ctas.length,
            abbreviations_found: uniqueAbbreviations.slice(0, 30),
            unique_text_colours: colours.size,
            unique_bg_colours: bgColours.size,
            page_height_px: document.documentElement.scrollHeight,
            viewport_height_px: window.innerHeight,
            scrollable_pages: Math.round(document.documentElement.scrollHeight / window.innerHeight * 10) / 10,
        };
    }
    """)
    return metrics


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
    "get_headings": _get_headings,
    "get_form_fields": _get_form_fields,
    "get_error_messages": _get_error_messages,
    "get_page_text": _get_page_text,
    "take_screenshot": _take_screenshot,
    "get_page_metrics": _get_page_metrics,
    "get_visible_text": _get_visible_text,
    "navigate_to": _navigate_to,
    "click_element": _click_element,
    "get_links": _get_links,
    "get_page_url": _get_page_url,
}
