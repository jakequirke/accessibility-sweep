# CLAUDE.md — accessibility-sweep

## Project Identity

**Name:** accessibility-sweep
**Purpose:** AI-powered accessibility auditing tool that sweeps websites using Playwright, analyses issues with axe-core, then runs persona-based behavioural testing (keyboard, screen reader, cognitive) via Claude API tool-use loops.
**Stack:** Python · Playwright · axe-core · Claude API (tool use) · BeautifulSoup4 · Jinja2 · Rich
**Target standard:** WCAG 2.2 AA (with WCAG 3.0 / APCA future-proofing)
**Output:** CLI-first → HTML report + JSON + plain text terminal summary
**Author:** Jake Quirke — Frontend Software Engineer & Accessibility Lead, Giant Digital

---

## Architecture Overview

The tool operates in two modes that run sequentially:

### Mode 1 — Static Analysis Pipeline (fast, deterministic, no AI tokens)

```
CLI Entry → Crawler (Playwright) → axe-core scan → Custom checks → Raw findings
```

This produces a baseline of automated findings. It runs first, always, and costs nothing.

### Mode 2 — Agent Personas (behavioural, AI-driven, per-persona)

```
Raw findings + Page → Agent Loop (Claude API tool use) → Persona findings
```

Each persona is an independent agent run. Claude receives a system prompt defining the persona, a set of Playwright-backed tools, and the page URL. It decides what to test, calls tools, reasons about results, and logs its own findings.

### Combined output

```
Static findings + Keyboard persona findings + Screen reader persona findings + Cognitive persona findings → Unified report
```

---

## Directory Structure

```
accessibility-sweep/
├── cli.py                          # Entry point
├── config.py                       # CLI args, env, defaults
├── .env                            # ANTHROPIC_API_KEY (gitignored)
│
├── crawler/
│   ├── spider.py                   # Site crawl from seed URL or manual URL list
│   └── filters.py                  # URL exclusion, depth limits, robots.txt
│
├── scanner/
│   ├── axe.py                      # axe-core via axe-playwright-python
│   ├── contrast.py                 # APCA + WCAG 2.x contrast checks
│   ├── headings.py                 # Heading hierarchy validation
│   ├── landmarks.py                # Landmark region checks
│   ├── focus.py                    # Focus visibility (static check)
│   └── aria.py                     # ARIA attribute validation
│
├── agent/
│   ├── loop.py                     # Tool-use agent loop (Claude API)
│   ├── personas.py                 # System prompts per persona
│   ├── tools.py                    # Tool definitions (JSON schema + dispatch)
│   └── context.py                  # Structured context assembly for each persona
│
├── browser/
│   ├── driver.py                   # Playwright lifecycle wrapper
│   ├── keyboard.py                 # Key press helpers, focus sequence capture
│   ├── aria_tree.py                # Accessibility tree extraction
│   ├── metrics.py                  # Page metric collection (word count, links, etc.)
│   └── screenshots.py              # Screenshot capture for cognitive analysis
│
├── reference/
│   ├── wcag22.json                 # All 78 WCAG 2.2 success criteria (structured)
│   ├── aria_patterns.json          # Expected keyboard behaviour per ARIA widget role
│   └── screen_reader_mappings.json # What screen readers announce for common HTML/ARIA combos
│
├── reporting/
│   ├── reporter.py                 # Aggregates all findings, deduplicates, sorts
│   ├── templates/
│   │   └── report.html.j2          # Jinja2 HTML report template
│   └── formatters.py               # JSON, plain text, terminal (Rich) formatters
│
└── tests/
    ├── test_scanner.py
    ├── test_agent.py
    └── fixtures/                   # Known-issue HTML pages for validation
```

---

## Core Principles

1. **Automated first, AI second.** axe-core and custom checks run before any API call. Never spend tokens on something a rule can catch instantly.
2. **Structured data in, reasoned findings out.** The AI never gets raw HTML and a vague instruction. It gets the accessibility tree, the focus sequence, computed metrics, and the specific WCAG criteria to evaluate against.
3. **Every finding must cite a WCAG success criterion.** No vague "this could be better" observations. Every logged issue references a specific SC with ID, name, and level.
4. **Personas are behavioural, not cosmetic.** Each persona has a restricted tool set that forces it to experience the page the way that user would. The keyboard persona cannot click. The screen reader persona cannot see screenshots.
5. **Tangible over theoretical.** Findings include what is wrong, who it affects, the WCAG reference, and a specific remediation suggestion with code where possible.

---

## Coding Conventions

### Python style
- Python 3.11+. Use type hints on all function signatures.
- Use `pathlib.Path` for all file paths, never string concatenation.
- Use `dataclasses` or `Pydantic` models for structured data (findings, page results, persona configs).
- Use `async/await` for Playwright operations and HTTP calls.
- Use `tenacity` for retry logic on API calls and flaky page loads.
- Keep functions short. A function that scrolls past one screen is too long.
- No abbreviations in variable names. Write `accessibility_tree` not `a11y_tree`, `success_criterion` not `sc`. Accessibility is always written in full.

### Naming
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions and variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- WCAG references: always `"1.4.3 Contrast (Minimum)"` format — number, name, in that order.

### Error handling
- Never silently swallow exceptions. Log them with `rich.console` and continue gracefully.
- Playwright timeouts should be caught and logged as "page unresponsive" rather than crashing the run.
- Claude API errors should retry (via tenacity) then log the failure and skip the persona for that page.

### Dependencies
- `playwright` — browser automation, DOM access, keyboard simulation, accessibility tree
- `axe-playwright-python` — axe-core engine via Playwright
- `beautifulsoup4` — HTML parsing for custom structural checks
- `httpx` — async HTTP for crawling
- `anthropic` — Claude API (official Python SDK)
- `jinja2` — HTML report templating
- `python-dotenv` — env/key management
- `rich` — terminal output
- `tenacity` — retry logic

---

## The Agent Loop

The agent loop lives in `agent/loop.py`. It implements Claude API tool use.

### How it works

```python
async def run_persona(persona: Persona, page_url: str, browser: BrowserDriver) -> list[Finding]:
    """
    Run a single persona against a single page.
    Returns a list of findings the persona discovered.
    """
    # 1. Capture structured context for this persona
    context = await persona.build_context(page_url, browser)

    # 2. Initialise message history with the persona system prompt
    messages = [{"role": "user", "content": context.to_prompt()}]

    # 3. Enter tool-use loop
    findings = []
    for step in range(persona.max_steps):
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=persona.system_prompt,
            tools=persona.tool_definitions,
            messages=messages,
        )

        # 4. Process response — may contain text, tool_use, or stop
        if response.stop_reason == "end_turn":
            # Extract any final findings from the response text
            findings.extend(parse_findings_from_response(response))
            break

        if response.stop_reason == "tool_use":
            # Execute each tool call against the browser
            tool_results = await execute_tool_calls(response, browser)
            # Append assistant response and tool results to messages
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    return findings
```

### Key rules for the agent loop

- **Use `claude-sonnet-4-20250514`** for persona runs. It is fast enough for multi-step tool use and good enough for accessibility reasoning. Reserve Opus for complex cognitive analysis if needed.
- **Cap steps per persona per page.** Default: 40 steps for keyboard, 30 for screen reader, 20 for cognitive. These are configurable via CLI.
- **Always pass the `log_issue` tool.** This is how Claude files findings. Parse these tool calls to build the findings list.
- **Pass `log_observation` for non-WCAG notes.** Qualitative observations that don't map to a specific SC but are still useful.
- **Include the page's axe-core results in the initial context** so the persona knows what's already been flagged and can focus on what automated tools missed.

---

## Persona Definitions

Each persona lives in `agent/personas.py` as a dataclass with a system prompt, allowed tools, context builder, and step limit.

### Keyboard Navigation Persona

**Identity:** A keyboard-only user who cannot use a mouse. Navigates exclusively with Tab, Shift+Tab, Enter, Space, Arrow keys, and Escape.

**Allowed tools:**
- `navigate(url)` — go to a page
- `press_key(key)` — Tab, Shift+Tab, Enter, Space, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Escape, Home, End
- `get_focus_state()` — returns the currently focused element: tag, role, accessible name, bounding box, whether focus indicator is visible, tabindex value
- `get_aria_tree()` — full accessibility tree snapshot
- `get_interactive_elements()` — list of all interactive elements with their DOM order position
- `log_issue(wcag_criterion, severity, description, element, remediation)`
- `log_observation(note)`
- `mark_complete()`

**Explicitly excluded tools:** `click_element`, `screenshot`. This persona cannot click and cannot see.

**Context provided on start:**
- The full DOM-order list of interactive elements (tag, role, name, tabindex, DOM position)
- The accessibility tree snapshot
- The axe-core findings for this page (so it knows what's already flagged)
- The relevant ARIA Authoring Practices Guide pattern for any widget roles found on the page

**What it evaluates:**
- WCAG 2.1.1 — Keyboard: Can every interactive element be reached and operated by keyboard alone?
- WCAG 2.1.2 — No Keyboard Trap: Can the user always move focus away from every component?
- WCAG 2.4.1 — Bypass Blocks: Is there a skip link or equivalent mechanism?
- WCAG 2.4.3 — Focus Order: Does the tab order match the visual/logical reading order?
- WCAG 2.4.7 — Focus Visible: Is there a visible focus indicator on every focused element?
- WCAG 2.4.11 — Focus Not Obscured (Minimum): Is the focused element at least partially visible (not behind sticky headers/modals)?
- WCAG 2.4.12 — Focus Not Obscured (Enhanced): Is the focused element fully visible?
- WCAG 3.2.1 — On Focus: Does anything unexpected happen when an element receives focus?

**Behavioural instructions (included in system prompt):**

```
You are a keyboard-only user testing this web page. You cannot use a mouse.
You must navigate exclusively using press_key. You cannot click anything.

Your testing procedure:
1. First, check for a skip link by pressing Tab once from the top of the page.
   - If a skip link exists, activate it and verify focus moves past the navigation.
   - If no skip link exists, log an issue against WCAG 2.4.1.

2. Tab through every interactive element on the page sequentially.
   For each element that receives focus:
   - Check get_focus_state() to confirm focus is visible (has a visible outline or indicator).
   - Check the accessible name is meaningful (not empty, not "click here", not "link").
   - Check the role matches the element's purpose.
   - Check focus is not obscured behind sticky elements.
   - Record the focus order sequence.

3. At each interactive widget (dropdown, modal trigger, tab panel, accordion, carousel):
   - Test the expected keyboard pattern from the ARIA Authoring Practices Guide.
   - For modals: verify focus moves into the modal, is trapped inside, Escape closes it,
     and focus returns to the trigger.
   - For dropdowns: verify Arrow keys move between options, Enter/Space selects,
     Escape closes.
   - For tab panels: verify Arrow keys move between tabs, the selected panel is shown.

4. After completing the tab sequence:
   - Compare your recorded focus order against the DOM-order list of interactive elements.
   - Flag any interactive elements you could not reach.
   - Flag any illogical order (e.g., focus jumps from header to footer, skipping main content).

5. Test reverse tab order (Shift+Tab) from the last element back to the first.
   Confirm it is the exact reverse of the forward order.

6. Log every issue found using log_issue with the specific WCAG criterion, severity,
   the affected element, and a remediation suggestion including code where appropriate.

Severity guide:
- critical: user cannot complete a core task (keyboard trap, unreachable form submit)
- major: significant barrier but workaround exists (missing skip link, poor focus order)
- minor: usable but degraded experience (weak focus indicator, slightly illogical order)
```

### Screen Reader Persona

**Identity:** A screen reader user who perceives the page through its accessibility tree — roles, names, states, and reading order. Cannot see the visual layout.

**Allowed tools:**
- `navigate(url)` — go to a page
- `get_aria_tree()` — the computed accessibility tree (roles, names, values, states, children, level)
- `get_page_text()` — visible text content in reading order (headings marked, landmarks marked)
- `get_element_announcement(selector)` — returns what a screen reader would announce for a specific element: role + name + state + value + description
- `get_live_regions()` — list of all ARIA live regions, their politeness, and current content
- `get_headings()` — ordered list of all headings with level, text, and nesting context
- `get_landmarks()` — all landmark regions with their roles and labels
- `get_form_fields()` — all form inputs with their labels, descriptions, required state, error state
- `press_key(key)` — for testing dynamic announcements (e.g., expanding an accordion then checking what's announced)
- `log_issue(wcag_criterion, severity, description, element, remediation)`
- `log_observation(note)`
- `mark_complete()`

**Explicitly excluded tools:** `screenshot`, `click_element`. This persona cannot see and does not use a mouse.

**Context provided on start:**
- The full accessibility tree snapshot
- The heading hierarchy
- All landmark regions
- All form fields with label associations
- All ARIA live regions
- The axe-core findings for this page
- The `screen_reader_mappings.json` reference (what common HTML/ARIA patterns announce as)

**What it evaluates:**
- WCAG 1.1.1 — Non-text Content: Do images have meaningful alt text? (Quality check — axe-core only checks presence.)
- WCAG 1.3.1 — Info and Relationships: Are visual relationships (headings, lists, tables, form groups) conveyed programmatically?
- WCAG 1.3.2 — Meaningful Sequence: Does the reading order (from the accessibility tree) make logical sense?
- WCAG 2.4.2 — Page Titled: Is the page title descriptive and unique?
- WCAG 2.4.4 — Link Purpose (In Context): Can a screen reader user understand each link's purpose from its name and surrounding context?
- WCAG 2.4.6 — Headings and Labels: Are headings and labels descriptive?
- WCAG 2.5.3 — Label in Name: Does the accessible name contain the visible label text?
- WCAG 3.3.2 — Labels or Instructions: Do all form inputs have clear, associated labels?
- WCAG 4.1.2 — Name, Role, Value: Do all interactive components have correct accessible names, roles, and states?
- WCAG 4.1.3 — Status Messages: Are dynamic status messages announced via ARIA live regions without stealing focus?

**Behavioural instructions (included in system prompt):**

```
You are a screen reader user testing this web page. You cannot see the visual layout.
You perceive the page entirely through its accessibility tree, announced roles, names,
and states. You navigate by headings, landmarks, and reading order.

Your testing procedure:
1. Review the page title. Is it descriptive and unique?

2. Review the landmark structure.
   - Is there a main landmark?
   - Is there a navigation landmark?
   - Are landmarks labelled when there are multiples of the same type?

3. Review the heading hierarchy.
   - Does it start with a single h1?
   - Does the hierarchy flow logically (no skipped levels)?
   - Are headings descriptive of their section content?
   - Would a screen reader user navigating by headings alone get a useful page outline?

4. Walk through the accessibility tree in reading order.
   For each element, evaluate:
   - Does the announced role match the element's visual/functional purpose?
   - Is the accessible name meaningful and not redundant (e.g., "image of image of logo")?
   - For images: does the alt text convey the same information a sighted user gets?
     (Not just "photo" — what is the photo of and why is it here?)
   - For links: would "link, [name]" make sense if heard in isolation?
     (Not "link, click here" or "link, read more".)
   - For buttons: does the name describe the action? (Not "button, submit" on a search form.)
   - For form fields: use get_form_fields() to check every input has a programmatically
     associated label, not just a visual one. Check for description (aria-describedby)
     on complex fields.

5. Check for ARIA misuse.
   - Are ARIA roles used on elements that already have the correct native semantics?
     (e.g., role="button" on a <button> is redundant.)
   - Are custom widgets using ARIA roles, states, and properties correctly?
   - Are aria-expanded, aria-selected, aria-checked states present where expected?

6. Test dynamic content.
   - If there are expandable sections, press_key to expand them, then check
     get_live_regions() and get_aria_tree() to see if the state change is announced.
   - Check that error messages on forms are associated with their fields and announced.

7. Evaluate the overall screen reader experience.
   - Would a user navigating this page by headings, landmarks, or tab key alone
     be able to understand the page purpose and complete the main task?
   - Are there any "mystery" elements — things with no name, wrong role, or confusing state?

Severity guide:
- critical: content or functionality is completely inaccessible (form with no labels,
  interactive widget with no name, images conveying critical info with no alt text)
- major: usable but confusing or degraded (vague link text, illogical heading order,
  missing landmark labels)
- minor: technically correct but could be improved (slightly verbose alt text,
  minor heading level skip in a sidebar)
```

### Cognitive Accessibility Persona

**Identity:** A user with cognitive disabilities who needs clear language, predictable interactions, simple layouts, and helpful error recovery. This persona evaluates meaning, clarity, and cognitive load.

**Allowed tools:**
- `navigate(url)` — go to a page
- `get_page_text()` — full visible text in reading order
- `get_page_metrics()` — returns computed metrics: total word count, unique word count, average sentence length, number of links, number of form fields, number of headings, number of images, presence of animations/carousels/autoplay, number of distinct calls to action, Flesch-Kincaid grade level, number of abbreviations/acronyms found
- `screenshot()` — full page screenshot for visual complexity assessment
- `get_form_fields()` — all form inputs with labels, descriptions, required state, error messages
- `get_headings()` — heading hierarchy
- `get_error_messages()` — any visible error messages on the page and their association to fields
- `log_issue(wcag_criterion, severity, description, element, remediation)`
- `log_observation(note)`
- `mark_complete()`

**Explicitly excluded tools:** `press_key` (this persona focuses on content/design, not input method), `get_aria_tree` (this persona evaluates what is perceived visually, not programmatically).

**Context provided on start:**
- The full page text content
- Computed page metrics (see above)
- A screenshot of the page
- All form fields and their current state
- Any error messages visible
- The axe-core findings for this page
- Relevant COGA (Cognitive and Learning Disabilities Accessibility) task force guidance

**What it evaluates:**
- WCAG 1.3.5 — Identify Input Purpose: Can form field purposes be programmatically determined (autocomplete attributes)?
- WCAG 2.2.1 — Timing Adjustable: Are there any time limits, and can they be extended?
- WCAG 2.4.2 — Page Titled: Is the page title clear and descriptive?
- WCAG 2.4.5 — Multiple Ways: Are there multiple ways to find content (nav, search, sitemap)?
- WCAG 2.4.6 — Headings and Labels: Are headings and labels descriptive (not clever/ambiguous)?
- WCAG 3.1.3 — Unusual Words: Are jargon, idioms, or technical terms explained?
- WCAG 3.1.4 — Abbreviations: Are abbreviations expanded or explained on first use?
- WCAG 3.1.5 — Reading Level: Is content written at a lower secondary education reading level where possible?
- WCAG 3.2.3 — Consistent Navigation: Is navigation consistent across pages?
- WCAG 3.2.4 — Consistent Identification: Are components with the same function identified consistently?
- WCAG 3.2.6 — Consistent Help: Is help/contact information in a consistent location?
- WCAG 3.3.1 — Error Identification: Are errors clearly identified in text?
- WCAG 3.3.2 — Labels or Instructions: Are form instructions provided before the form, not after?
- WCAG 3.3.3 — Error Suggestion: Do error messages suggest how to fix the problem?
- WCAG 3.3.4 — Error Prevention: For important submissions, can the user review, confirm, or reverse?
- WCAG 3.3.7 — Redundant Entry: Is the user asked to re-enter information they already provided?
- WCAG 3.3.8 — Accessible Authentication (Minimum): Can the user authenticate without a cognitive function test?
- WCAG 3.3.9 — Accessible Authentication (Enhanced): No cognitive test at all for authentication?

**Behavioural instructions (included in system prompt):**

```
You are evaluating this page from the perspective of a user with cognitive disabilities.
You assess language clarity, interaction predictability, visual complexity, error handling,
and overall cognitive load.

Your testing procedure:
1. Review page metrics from get_page_metrics().
   - Flesch-Kincaid grade level above 9 is a concern. Above 12 is a major issue.
   - Average sentence length above 25 words is a concern.
   - More than 3 distinct calls to action on a single page is a concern.
   - More than 15 links visible simultaneously is a concern for decision fatigue.
   - Any autoplaying content (video, carousel, animation) is a concern.

2. Read the page text from get_page_text().
   - Identify sentences or passages that use jargon, idioms, metaphors, or
     unnecessarily complex vocabulary.
   - Identify abbreviations or acronyms that are not expanded on first use.
   - Identify instructions that are vague, ambiguous, or assume prior knowledge.
   - For each issue, suggest a plain language alternative.

3. Review the screenshot for visual complexity.
   - Is the page layout clean and predictable?
   - Are related items visually grouped?
   - Is there excessive visual noise (too many competing elements, colours, or fonts)?
   - Is important content clearly distinguishable from secondary content?
   - Are interactive elements obviously interactive (buttons look like buttons)?

4. If the page contains forms, evaluate using get_form_fields() and get_error_messages().
   - Are labels clear and positioned before or above their fields?
   - Are required fields clearly marked (not just with colour)?
   - Are instructions provided before the form, not after or on submission?
   - If there are error messages: are they specific, actionable, and positioned
     near the field they relate to?
   - Is the user asked to re-enter information they already provided on a previous page?
   - Are there autocomplete attributes on appropriate fields (name, email, address, etc.)?

5. Evaluate consistency (requires knowledge of other pages on the site if available).
   - Is the navigation in the same location and order as other pages?
   - Are similar components (search, help links, contact info) in consistent positions?

6. Evaluate cognitive load holistically.
   - Could a user under stress, distraction, or cognitive fatigue complete the main
     task on this page?
   - Are there unnecessary steps, redundant content, or decisions that could be eliminated?
   - Does the page respect the user's time and attention?

7. Check the COGA guidance areas:
   - Provide help and support: is there a clear way to get help?
   - Support personalisation: can the user adjust the experience?
   - Use clear and understandable content: is the content plain?
   - Make it easy to find what you need: is the information architecture logical?
   - Help users avoid mistakes: are destructive actions guarded?
   - Support understanding of processes: are multi-step processes clearly indicated?

Severity guide:
- critical: page is incomprehensible or task is impossible without specialist knowledge
  (form with no labels, error messages that don't explain the problem, no way to get help)
- major: page is confusing or frustrating (jargon without explanation, grade level 12+,
  too many competing calls to action, vague error messages)
- minor: page is understandable but could be clearer (slightly complex sentences,
  minor jargon, abbreviation not expanded)
```

---

## The Journey Persona (Multi-Page)

Beyond per-page personas, the tool supports a **journey mode** where a persona navigates across multiple pages to complete a task (e.g., "donate to this charity" or "find contact information").

Journey mode works by:
1. Giving the persona a goal (e.g., "Complete a donation of £10") and a start URL.
2. The persona has access to `navigate(url)` and can follow links.
3. The persona evaluates each page it visits through its accessibility lens.
4. At the end, the persona produces a journey report: pages visited, issues per page, and an overall assessment of whether the task was completable.

Journey definitions live in a `journeys.json` config file:

```json
{
  "journeys": [
    {
      "name": "Donation Flow",
      "start_url": "/",
      "goal": "Navigate to the donation page and complete a £10 donation.",
      "personas": ["keyboard", "screen_reader", "cognitive"],
      "max_pages": 5
    },
    {
      "name": "Find Contact Info",
      "start_url": "/",
      "goal": "Find the organisation's phone number and email address.",
      "personas": ["keyboard", "cognitive"],
      "max_pages": 3
    }
  ]
}
```

---

## Tool Implementations

Each tool is a Python async function that wraps Playwright. Tool definitions follow the Claude API tool-use schema.

### Tool: `press_key`

```python
async def press_key(browser: BrowserDriver, key: str) -> dict:
    """Press a keyboard key and return the resulting focus state."""
    valid_keys = {
        "Tab", "Shift+Tab", "Enter", "Space", "Escape",
        "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
        "Home", "End", "PageUp", "PageDown"
    }
    if key not in valid_keys:
        return {"error": f"Invalid key: {key}. Valid keys: {', '.join(sorted(valid_keys))}"}

    page = browser.page
    await page.keyboard.press(key)
    await page.wait_for_timeout(150)  # Brief pause for focus/state to settle

    return await get_focus_state(browser)
```

### Tool: `get_focus_state`

```python
async def get_focus_state(browser: BrowserDriver) -> dict:
    """Return detailed information about the currently focused element."""
    page = browser.page
    state = await page.evaluate("""() => {
        const el = document.activeElement;
        if (!el || el === document.body) {
            return { focused: false, element: "body (no focus)" };
        }

        const rect = el.getBoundingClientRect();
        const styles = window.getComputedStyle(el);
        const outlineWidth = parseFloat(styles.outlineWidth) || 0;
        const outlineStyle = styles.outlineStyle;
        const boxShadow = styles.boxShadow;

        // Detect if focus indicator is visible
        const hasOutline = outlineStyle !== "none" && outlineWidth > 0;
        const hasBoxShadow = boxShadow !== "none" && boxShadow !== "";
        const focusVisible = hasOutline || hasBoxShadow;

        // Check if element is obscured by sticky/fixed elements
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const topElement = document.elementFromPoint(centerX, centerY);
        const isObscured = topElement !== el && !el.contains(topElement);

        return {
            focused: true,
            tag: el.tagName.toLowerCase(),
            role: el.getAttribute("role") || el.tagName.toLowerCase(),
            accessible_name: el.getAttribute("aria-label")
                || el.getAttribute("aria-labelledby")
                || el.innerText?.substring(0, 100)
                || el.getAttribute("alt")
                || el.getAttribute("title")
                || "",
            tabindex: el.getAttribute("tabindex"),
            type: el.getAttribute("type") || null,
            href: el.getAttribute("href") || null,
            aria_expanded: el.getAttribute("aria-expanded"),
            aria_selected: el.getAttribute("aria-selected"),
            aria_checked: el.getAttribute("aria-checked"),
            aria_disabled: el.getAttribute("aria-disabled"),
            focus_visible: focusVisible,
            is_obscured: isObscured,
            bounding_box: {
                top: rect.top,
                left: rect.left,
                width: rect.width,
                height: rect.height
            },
            in_viewport: rect.top >= 0 && rect.top <= window.innerHeight
        };
    }""")
    return state
```

### Tool: `get_aria_tree`

```python
async def get_aria_tree(browser: BrowserDriver) -> dict:
    """Return the computed accessibility tree from Playwright."""
    page = browser.page
    snapshot = await page.accessibility.snapshot()
    return snapshot or {"error": "No accessibility tree available"}
```

### Tool: `get_page_metrics`

```python
async def get_page_metrics(browser: BrowserDriver) -> dict:
    """Compute cognitive load metrics for the current page."""
    page = browser.page
    metrics = await page.evaluate("""() => {
        const body = document.body;
        const text = body.innerText || "";
        const words = text.split(/\\s+/).filter(w => w.length > 0);
        const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 0);
        const links = document.querySelectorAll("a[href]");
        const formFields = document.querySelectorAll("input, select, textarea");
        const headings = document.querySelectorAll("h1, h2, h3, h4, h5, h6");
        const images = document.querySelectorAll("img");
        const videos = document.querySelectorAll("video, iframe[src*='youtube'], iframe[src*='vimeo']");
        const animations = document.querySelectorAll("[class*='animate'], [class*='carousel'], [class*='slider'], [class*='marquee']");
        const autoplay = document.querySelectorAll("video[autoplay], audio[autoplay]");
        const ctas = document.querySelectorAll("a.btn, a.button, button, [role='button'], input[type='submit']");
        const abbreviations = text.match(/\\b[A-Z]{2,}\\b/g) || [];

        return {
            word_count: words.length,
            unique_words: [...new Set(words.map(w => w.toLowerCase()))].length,
            sentence_count: sentences.length,
            average_sentence_length: sentences.length > 0
                ? Math.round(words.length / sentences.length) : 0,
            link_count: links.length,
            form_field_count: formFields.length,
            heading_count: headings.length,
            image_count: images.length,
            video_count: videos.length,
            has_animations: animations.length > 0,
            has_autoplay: autoplay.length > 0,
            call_to_action_count: ctas.length,
            abbreviations_found: [...new Set(abbreviations)]
        };
    }""")

    # Compute Flesch-Kincaid in Python for accuracy
    text = await page.inner_text("body")
    metrics["flesch_kincaid_grade"] = compute_flesch_kincaid(text)

    return metrics
```

### Tool: `get_element_announcement`

```python
async def get_element_announcement(browser: BrowserDriver, selector: str) -> dict:
    """
    Simulate what a screen reader would announce for a given element.
    Uses the accessibility tree node for the element.
    """
    page = browser.page
    announcement = await page.evaluate("""(selector) => {
        const el = document.querySelector(selector);
        if (!el) return { error: "Element not found" };

        const role = el.getAttribute("role")
            || el.tagName.toLowerCase();
        const name = el.getAttribute("aria-label")
            || el.getAttribute("aria-labelledby")
            || el.innerText?.substring(0, 200)
            || el.getAttribute("alt")
            || el.getAttribute("title")
            || "(no name)";
        const state_parts = [];
        if (el.getAttribute("aria-expanded") === "true") state_parts.push("expanded");
        if (el.getAttribute("aria-expanded") === "false") state_parts.push("collapsed");
        if (el.getAttribute("aria-selected") === "true") state_parts.push("selected");
        if (el.getAttribute("aria-checked") === "true") state_parts.push("checked");
        if (el.getAttribute("aria-checked") === "false") state_parts.push("not checked");
        if (el.hasAttribute("required") || el.getAttribute("aria-required") === "true")
            state_parts.push("required");
        if (el.getAttribute("aria-disabled") === "true") state_parts.push("dimmed");
        if (el.getAttribute("aria-invalid") === "true") state_parts.push("invalid");
        const description = el.getAttribute("aria-describedby")
            ? document.getElementById(el.getAttribute("aria-describedby"))?.innerText
            : null;

        const announcement = [name, role, ...state_parts]
            .filter(Boolean).join(", ");

        return {
            selector: selector,
            role: role,
            name: name,
            states: state_parts,
            description: description,
            announcement: announcement,
            would_hear: `"${announcement}"`
        };
    }""", selector)
    return announcement
```

### Tool: `log_issue`

```python
async def log_issue(
    wcag_criterion: str,
    severity: str,
    description: str,
    element: str,
    remediation: str,
) -> dict:
    """
    Log an accessibility issue found during persona testing.
    This is called by Claude during the agent loop — it is how
    the persona reports findings.
    """
    valid_severities = {"critical", "major", "minor"}
    if severity not in valid_severities:
        return {"error": f"Invalid severity: {severity}. Use: {', '.join(valid_severities)}"}

    finding = Finding(
        wcag_criterion=wcag_criterion,
        severity=severity,
        description=description,
        element=element,
        remediation=remediation,
        source="agent",
        persona=current_persona_name,
    )
    findings_store.append(finding)
    return {"logged": True, "finding_id": len(findings_store)}
```

---

## Reference Data Files

### `reference/aria_patterns.json`

Maps ARIA widget roles to their expected keyboard interaction patterns. Used by the keyboard persona to know what behaviour to test.

```json
{
  "dialog": {
    "description": "Modal dialog",
    "expected_keyboard": {
      "Tab": "Moves focus between focusable elements inside the dialog",
      "Shift+Tab": "Moves focus backwards inside the dialog",
      "Escape": "Closes the dialog, returns focus to the trigger element"
    },
    "focus_rules": [
      "On open: focus moves to the first focusable element inside the dialog",
      "Focus must be trapped inside the dialog while open",
      "On close: focus returns to the element that triggered the dialog"
    ]
  },
  "menu": {
    "description": "Navigation or action menu",
    "expected_keyboard": {
      "ArrowDown": "Move to next menu item",
      "ArrowUp": "Move to previous menu item",
      "Enter": "Activate the focused menu item",
      "Escape": "Close the menu, return focus to trigger",
      "Home": "Move to first menu item",
      "End": "Move to last menu item"
    }
  },
  "tablist": {
    "description": "Tab panel widget",
    "expected_keyboard": {
      "ArrowRight": "Move to next tab (horizontal tablist)",
      "ArrowLeft": "Move to previous tab (horizontal tablist)",
      "ArrowDown": "Move to next tab (vertical tablist)",
      "ArrowUp": "Move to previous tab (vertical tablist)",
      "Home": "Move to first tab",
      "End": "Move to last tab"
    },
    "focus_rules": [
      "Only the active tab is in the tab order (tabindex=0)",
      "Inactive tabs have tabindex=-1",
      "Arrow keys move between tabs, Tab moves to the tab panel content"
    ]
  },
  "combobox": {
    "description": "Combo box / autocomplete input",
    "expected_keyboard": {
      "ArrowDown": "Open the listbox and move to next option",
      "ArrowUp": "Move to previous option",
      "Enter": "Select the focused option",
      "Escape": "Close the listbox without selecting"
    }
  },
  "accordion": {
    "description": "Expandable content sections",
    "expected_keyboard": {
      "Enter": "Toggle the focused section open or closed",
      "Space": "Toggle the focused section open or closed"
    },
    "focus_rules": [
      "Each accordion header should be focusable",
      "aria-expanded reflects the open/closed state"
    ]
  },
  "carousel": {
    "description": "Content carousel / slideshow",
    "expected_keyboard": {
      "ArrowRight": "Move to next slide",
      "ArrowLeft": "Move to previous slide",
      "Tab": "Move focus to controls or content within the current slide"
    },
    "focus_rules": [
      "Autoplay must be pausable via keyboard",
      "Current slide indicator should be announced"
    ]
  }
}
```

### `reference/screen_reader_mappings.json`

Maps common HTML/ARIA combinations to what screen readers would announce. The screen reader persona uses this to compare the actual accessible name/role against what users expect to hear.

```json
{
  "patterns": [
    {
      "html": "<button>Submit</button>",
      "announces_as": "Submit, button",
      "notes": "Native button with text content."
    },
    {
      "html": "<a href='/about'>About us</a>",
      "announces_as": "About us, link",
      "notes": "Standard link. Name comes from text content."
    },
    {
      "html": "<input type='text' id='email' aria-label='Email address'>",
      "announces_as": "Email address, edit text",
      "notes": "aria-label overrides any visual label for screen readers."
    },
    {
      "html": "<div role='alert'>Your form has errors.</div>",
      "announces_as": "alert, Your form has errors.",
      "notes": "Announced immediately when content appears. No focus change."
    },
    {
      "html": "<input type='checkbox' checked aria-label='Agree to terms'>",
      "announces_as": "Agree to terms, checkbox, checked",
      "notes": "Checked state announced after role."
    },
    {
      "html": "<button aria-expanded='false'>Menu</button>",
      "announces_as": "Menu, button, collapsed",
      "notes": "aria-expanded=false announced as collapsed."
    },
    {
      "html": "<nav aria-label='Main'>...</nav>",
      "announces_as": "Main, navigation",
      "notes": "Landmark with label. Screen readers announce on entry."
    },
    {
      "html": "<img src='photo.jpg' alt=''>",
      "announces_as": "(nothing — image is decorative)",
      "notes": "Empty alt means screen readers skip the image entirely."
    },
    {
      "html": "<img src='photo.jpg'>",
      "announces_as": "photo.jpg, image",
      "notes": "Missing alt — screen reader reads filename. Always a failure."
    },
    {
      "html": "<div role='tab' aria-selected='true'>Settings</div>",
      "announces_as": "Settings, tab, selected, 3 of 5",
      "notes": "Tab role announces selection state and position in set."
    }
  ]
}
```

---

## CLI Interface

```bash
# Full scan: static analysis + all personas
python cli.py --url https://example.com

# Static analysis only (no AI, no tokens)
python cli.py --url https://example.com --static-only

# Single persona
python cli.py --url https://example.com --persona keyboard
python cli.py --url https://example.com --persona screen-reader
python cli.py --url https://example.com --persona cognitive

# Multiple specific personas
python cli.py --url https://example.com --persona keyboard --persona cognitive

# Full site crawl with depth limit
python cli.py --url https://example.com --depth 3 --delay 1.5

# Journey mode
python cli.py --url https://example.com --journey "Donation Flow" --journeys-file journeys.json

# Manual URL list
python cli.py --urls https://example.com/page-1 https://example.com/page-2

# Output options
python cli.py --url https://example.com --output-dir ./reports --format html,json,txt

# Exclude patterns
python cli.py --url https://example.com --exclude "/admin/*" --exclude "/api/*"

# Step limits for agent personas
python cli.py --url https://example.com --max-steps 50
```

---

## Reporting

The unified report combines static analysis and persona findings. Structure:

### Per page:
1. **Summary** — page URL, title, overall severity, pass/fail counts
2. **Automated findings** — from axe-core and custom checks (grouped by severity)
3. **Keyboard persona findings** — from agent run (grouped by severity)
4. **Screen reader persona findings** — from agent run (grouped by severity)
5. **Cognitive persona findings** — from agent run (grouped by severity)
6. **Journey findings** — if journey mode was used, cross-page issues

### Each finding includes:
- WCAG success criterion (ID + name + level)
- Severity (critical / major / minor)
- Description of the issue (plain language)
- Who it affects
- The specific element or content
- Remediation suggestion (with code example where applicable)
- Source (axe-core / custom check / keyboard persona / screen reader persona / cognitive persona)

### Deduplication:
If axe-core and a persona both flag the same issue on the same element, keep the persona's version (it will have richer context) and note that it was also flagged by automated scanning.

---

## Data Models

```python
@dataclass
class Finding:
    wcag_criterion: str          # e.g. "2.4.7 Focus Visible"
    severity: str                # "critical", "major", "minor"
    description: str             # Plain language description
    element: str                 # CSS selector or element description
    remediation: str             # How to fix it, with code if applicable
    source: str                  # "axe-core", "custom", "agent"
    persona: str | None = None   # "keyboard", "screen_reader", "cognitive", None
    who_affected: str = ""       # e.g. "Keyboard-only users"
    wcag_level: str = ""         # "A", "AA", "AAA"
    page_url: str = ""


@dataclass
class PageResult:
    url: str
    title: str
    scan_date: str
    axe_findings: list[Finding]
    custom_findings: list[Finding]
    persona_findings: dict[str, list[Finding]]  # persona_name -> findings
    metrics: dict | None = None  # Cognitive metrics if collected


@dataclass
class JourneyResult:
    name: str
    goal: str
    personas_run: list[str]
    pages_visited: list[str]
    completed: bool
    findings: list[Finding]
    narrative: str  # Claude's summary of the journey experience
```

---

## Performance and Token Management

- **Static analysis costs zero tokens.** Always run it.
- **Each persona run on a single page costs roughly 5,000–15,000 input tokens and 2,000–5,000 output tokens**, depending on page complexity and step count.
- **For a 10-page site with all 3 personas**, expect approximately 300,000–600,000 tokens total. Budget accordingly.
- **Cache the accessibility tree, page text, and metrics** — multiple personas may need the same data. Capture once, share across persona runs.
- **The `--static-only` flag exists for a reason.** Use it for quick sweeps where AI analysis is not needed.

---

## Testing the Tool

Maintain a `tests/fixtures/` directory with minimal HTML pages containing known accessibility issues. Each fixture should have a companion JSON file listing the expected findings.

```
tests/fixtures/
├── keyboard_trap.html              # A page with a keyboard trap
├── keyboard_trap_expected.json     # Expected findings
├── missing_labels.html             # Form with no labels
├── missing_labels_expected.json
├── poor_heading_order.html         # Skipped heading levels
├── poor_heading_order_expected.json
├── complex_language.html           # Grade level 14+ content
├── complex_language_expected.json
└── good_page.html                  # A page with no issues (control)
```

Run the tool against fixtures and compare output to expected findings. This validates both static analysis and persona accuracy.

---

## What This Is Not

This tool is an aid, not a replacement for manual accessibility testing. It catches a significant portion of issues automatically and uses AI to evaluate things that rules cannot, but it cannot fully replicate the experience of a real screen reader user, a real keyboard user, or a real person with cognitive disabilities.

Every report should include a note: "This automated and AI-assisted audit covers approximately 60–70% of WCAG 2.2 AA criteria. A manual audit by a qualified accessibility specialist is recommended to verify findings and catch issues that require human judgement."

Jake is that specialist. This tool makes his work faster and more consistent. It does not make him redundant.