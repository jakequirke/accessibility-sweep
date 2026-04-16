# Accessibility Audit Tool — Implementation Plan
**Project:** accessibility-sweep
**Stack:** Python · Playwright · axe-core · Claude API  
**Target:** WCAG 2.2 AA
**Output:** CLI-first, HTML report + JSON + plain text summary

---

## 1. Architecture Overview

The tool operates in two modes that run sequentially:

### Mode 1 — Static Analysis Pipeline (fast, deterministic, no AI tokens)

```
CLI Entry Point
    │
    ├── Crawler (Playwright)
    │     ├── Auto-crawl from seed URL (follows internal links)
    │     └── Manual URL list override
    │
    ├── Axe-core Scanner (per page)
    │     └── WCAG 2.2 AA automated checks
    │
    └── Custom Checks (per page)
          ├── APCA colour contrast (enhanced)
          ├── Heading structure
          ├── Landmark regions
          ├── Focus visibility (keyboard simulation)
          └── ARIA context analysis
```

This produces a baseline of automated findings. It runs first, always, and costs zero tokens.

### Mode 2 — Agent Personas (behavioural, AI-driven, per-persona)

```
Static findings + Page → Agent Loop (Claude API tool use) → Persona findings
```

Each persona is an independent agent run. Claude receives a system prompt defining the persona, a restricted set of Playwright-backed tools, and the page URL. It decides what to test, calls tools, reasons about results, and logs its own findings.

There are three per-page personas and one cross-page persona:

| Persona | Perspective | Key tools | What it catches |
|---|---|---|---|
| **Keyboard** | Keyboard-only user (no mouse) | `press_key`, `get_focus_state`, `get_focusable_elements` | Keyboard traps, missing skip links, invisible focus, illogical tab order, inaccessible widgets |
| **Screen Reader** | Non-visual user (accessibility tree only) | `get_accessibility_tree`, `get_page_text`, `get_element_details`, `get_live_regions` | Missing accessible names, incorrect roles, poor heading structure, broken live regions, label-in-name mismatches |
| **Cognitive** | User with cognitive disabilities | `take_screenshot`, `get_page_metrics`, `get_page_text`, `get_form_fields` | Complex language, high reading level, unclear error messages, visual clutter, missing autocomplete |
| **Journey** | Multi-page flow tester | `navigate_to`, `click_element`, `get_links` + keyboard/screen reader tools | Inconsistent navigation, non-unique page titles, broken cross-page keyboard flows |

### Combined output

```
Static findings + Persona findings → Unified report
    │
    └── Report Generator
          ├── HTML report (grouped by page + severity)
          ├── JSON output (structured, for future integration)
          └── Plain text terminal summary
```

### Optional: Claude API Enrichment

A lighter-weight AI mode (`--claude`) that sends page HTML + axe results to Claude for contextual analysis (alt text quality, ARIA context, plain language, remediation suggestions) without the full agent loop.

---

## 2. Recommended Libraries

| Library | Purpose | Why |
|---|---|---|
| `playwright` (Python) | Browser automation, DOM access, keyboard simulation | Most reliable for modern JS-heavy sites. Better than Selenium for this use case. |
| `axe-playwright-python` | Run axe-core engine via Playwright in Python | Direct Python wrapper — no Node bridge needed. Covers WCAG 2.0/2.1/2.2 automated rules. |
| `beautifulsoup4` | HTML parsing for custom checks | Lightweight, familiar, good for structural analysis outside the browser |
| `httpx` | Async HTTP for crawling | Faster than requests, async-native, respects robots.txt |
| `anthropic` | Claude API for AI enrichment | Official Python SDK |
| `jinja2` | HTML report templating | Clean separation of report logic from template |
| `python-dotenv` | API key management | Keeps credentials out of code |
| `rich` | Terminal output formatting | Makes plain text summary readable and professional |
| `tenacity` | Retry logic for API rate limits | Handles both Claude and crawling rate limits cleanly |

**Contrast checker:** The enhanced contrast algorithm is ported from the reference JS implementation — covered in Section 5.

---

## 3. Project Folder Structure

```
accessibility-sweep/
│
├── .env                        # API keys (never committed)
├── .env.example                # Template for setup
├── .gitignore
├── README.md
├── pyproject.toml              # Dependencies and packaging
│
├── cli.py                      # Entry point — argument parsing
│
├── accessibility_sweep/
│   ├── __init__.py
│   │
│   ├── crawler/
│   │   ├── __init__.py
│   │   ├── auto.py             # Auto-crawl from seed URL
│   │   └── manual.py           # Accept list of URLs
│   │
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── axe.py              # axe-core runner via Playwright
│   │   ├── apca.py             # APCA contrast implementation
│   │   ├── structure.py        # Headings, landmarks, forms
│   │   ├── keyboard.py         # Focus/keyboard simulation checks
│   │   └── element_context.py  # Enrich issues with DOM location context
│   │
│   ├── agent/                   # AI agent personas (Mode 2)
│   │   ├── __init__.py
│   │   ├── core.py             # Agent loop — Claude API tool-use loop
│   │   ├── tools.py            # Tool definitions + execution dispatch
│   │   └── personas/
│   │       ├── __init__.py
│   │       ├── keyboard.py     # Keyboard-only navigation persona
│   │       ├── screen_reader.py # Screen reader / accessibility tree persona
│   │       ├── cognitive.py    # Cognitive load / plain language persona
│   │       └── journey.py      # Multi-page journey persona
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── enrichment.py       # Claude API calls per page (lighter mode)
│   │   └── prompts.py          # All system/user prompt templates
│   │
│   ├── reporter/
│   │   ├── __init__.py
│   │   ├── html.py             # HTML report generator
│   │   ├── json_out.py         # JSON output
│   │   ├── terminal.py         # Plain text terminal summary
│   │   └── templates/
│   │       └── report.html     # Jinja2 HTML template
│   │
│   ├── models.py               # Dataclasses: Issue, PageResult, Report
│   ├── analyzer.py             # Site-wide issue deduplication
│   └── wcag_lookup.py          # WCAG 2.2 criterion metadata enrichment
│
├── reference/
│   ├── aria_patterns.json       # Expected keyboard behaviour per ARIA widget role
│   └── screen_reader_mappings.json # What screen readers announce for common HTML/ARIA
│
└── outputs/                   # Generated reports land here
```

---

## 4. Phased Build Plan

### Phase 1 — Skeleton + Single Page Scan
*Goal: prove the concept on one URL*

- Set up project with `pyproject.toml` and `.env`
- Playwright opens a single URL
- axe-core runs and returns violations
- Plain text summary prints to terminal
- No Claude API yet

**Done when:** `python cli.py --url https://example.com` prints a list of axe violations.

---

### Phase 2 — Custom Checks + Contrast
*Goal: go beyond what axe-core catches*

- Implement enhanced contrast checker (see Section 6)
- Add heading structure check (h1→h2→h3 order, single h1)
- Add landmark regions check (main, nav, header, footer present)
- Add form label check (inputs without associated labels)
- Merge results from axe and custom checks into unified Issue model

**Done when:** tool catches issues Lighthouse misses on a test site.

---

### Phase 3 — Full Site Crawler
*Goal: sweep an entire website from one URL*

- Auto-crawler follows internal links from seed URL
- Respects `robots.txt`
- Deduplicates URLs
- Accepts `--urls` flag for manual list override
- Handles rate limiting with delay between page visits
- Progress shown in terminal via `rich`

**Done when:** `python cli.py --url https://client-site.com` crawls all pages and scans each.

---

### Phase 4 — Claude API Enrichment
*Goal: contextual analysis axe cannot do*

- Integrate Claude API via `anthropic` SDK
- Per page: send HTML snapshot + axe results to Claude
- Claude evaluates: alt text quality, ARIA context, plain language, cognitive load
- Claude provides specific remediation per issue
- Rate limiting handled with `tenacity`

**Done when:** Claude adds contextual issues and remediation text to each page result.

---

### Phase 5 — Report Generation
*Goal: professional output in all three formats*

- HTML report via Jinja2 template — grouped by page, sorted by severity
- JSON output — full structured data for future integration
- Terminal summary already exists from Phase 1, polish it

**Done when:** full report saved to `/outputs/` after every run.

---

### Phase 6 — Hardening
*Goal: ready for real client use*

- Error handling for unreachable pages, auth-blocked pages, timeouts
- `--exclude` flag for URLs to skip
- `--depth` flag to limit crawl depth
- `--delay` flag for rate limiting on large sites
- Basic config file support (`accessibility-sweep.config.json`)

---

### Phase 7 — Agent Personas (Behavioural Testing)
*Goal: AI-driven testing that experiences the page the way real users do*

- Agent loop (`agent/core.py`) — Claude API tool-use loop that drives Playwright via structured tool calls
- Per-persona tool sets — each persona can only use tools that match its perspective (keyboard persona cannot click, screen reader persona cannot see screenshots)
- Three per-page personas: keyboard navigation, screen reader, cognitive load
- One cross-page persona: multi-page journey tester
- Each persona receives existing axe-core findings to avoid duplication
- Reference data files feed ARIA keyboard patterns and screen reader announcement mappings into context
- Findings parsed from Claude's structured JSON output into the unified `Issue` model

**Done when:** `python cli.py --url https://example.com --agent all` runs all four personas and merges findings into the report.

---

## 5. Key Code Patterns

### CLI Entry Point (`cli.py`)

```python
import argparse
from accessibility_sweep.crawler.auto import AutoCrawler
from accessibility_sweep.crawler.manual import ManualCrawler
from accessibility_sweep.scanner.axe import AxeScanner
from accessibility_sweep.reporter.terminal import print_summary

def main():
    parser = argparse.ArgumentParser(description="accessibility-sweep accessibility auditor")
    parser.add_argument("--url", help="Seed URL to auto-crawl from")
    parser.add_argument("--urls", nargs="+", help="Manual list of URLs to scan")
    parser.add_argument("--output", default="outputs/", help="Output directory")
    parser.add_argument("--depth", type=int, default=5, help="Max crawl depth")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between pages (seconds)")
    args = parser.parse_args()

    if args.urls:
        urls = args.urls
    elif args.url:
        crawler = AutoCrawler(args.url, max_depth=args.depth, delay=args.delay)
        urls = crawler.crawl()
    else:
        parser.error("Provide either --url or --urls")

    # Scan each URL
    scanner = AxeScanner()
    results = [scanner.scan(url) for url in urls]
    print_summary(results)

if __name__ == "__main__":
    main()
```

---

### Auto Crawler (`crawler/auto.py`)

```python
import httpx
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import time

class AutoCrawler:
    def __init__(self, seed_url: str, max_depth: int = 5, delay: float = 1.0):
        self.seed_url = seed_url
        self.base_domain = urlparse(seed_url).netloc
        self.max_depth = max_depth
        self.delay = delay
        self.visited = set()
        self.robots = self._load_robots(seed_url)

    def _load_robots(self, url: str) -> RobotFileParser:
        rp = RobotFileParser()
        robots_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt"
        rp.set_url(robots_url)
        try:
            rp.read()
        except Exception:
            pass
        return rp

    def _is_internal(self, url: str) -> bool:
        return urlparse(url).netloc == self.base_domain

    def _is_allowed(self, url: str) -> bool:
        return self.robots.can_fetch("*", url)

    def crawl(self) -> list[str]:
        queue = [(self.seed_url, 0)]
        found = []

        while queue:
            url, depth = queue.pop(0)
            if url in self.visited or depth > self.max_depth:
                continue
            if not self._is_allowed(url):
                continue

            self.visited.add(url)
            found.append(url)
            print(f"Found: {url}")
            time.sleep(self.delay)

            try:
                response = httpx.get(url, follow_redirects=True, timeout=10)
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                for link in soup.find_all("a", href=True):
                    absolute = urljoin(url, link["href"])
                    if self._is_internal(absolute) and absolute not in self.visited:
                        queue.append((absolute, depth + 1))
            except Exception as e:
                print(f"Could not fetch {url}: {e}")

        return found
```

---

### Axe Scanner (`scanner/axe.py`)

```python
from playwright.sync_api import sync_playwright
from axe_playwright_python.sync_playwright import Axe

def scan_page(url: str) -> dict:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        
        axe = Axe()
        results = axe.run(page)
        browser.close()
        
    return {
        "url": url,
        "violations": results["violations"],
        "incomplete": results["incomplete"],
    }
```

---

### APCA Implementation (`scanner/apca.py`)

No Python library exists, so here is the algorithm ported directly from the official JS reference (apca-w3 v0.0.98G):

```python
def srgb_to_y(hex_color: str) -> float:
    """Convert hex colour to APCA luminance value."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255

    # Linearise
    r = pow(r, 2.4)
    g = pow(g, 2.4)
    b = pow(b, 2.4)

    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b

    # Black clamp
    if y < 0.022:
        y += pow(0.022 - y, 1.414)

    return y


def apca_contrast(text_hex: str, bg_hex: str) -> float:
    """
    Returns APCA Lc contrast value.
    Positive = dark text on light background.
    Negative = light text on dark background.
    Absolute value used for pass/fail evaluation.
    """
    y_text = srgb_to_y(text_hex)
    y_bg = srgb_to_y(bg_hex)

    c = 1.14

    if y_bg > y_text:
        # Normal (dark text on light background)
        c *= pow(y_bg, 0.56) - pow(y_text, 0.57)
    else:
        # Reverse (light text on dark background)
        c *= pow(y_bg, 0.65) - pow(y_text, 0.62)

    if abs(c) < 0.1:
        return 0.0
    elif c > 0:
        c -= 0.027
    else:
        c += 0.027

    return round(c * 100, 2)


def apca_passes(lc_value: float, font_size_px: float, font_weight: int) -> bool:
    """
    Basic APCA pass/fail for body text.
    Reference: apca-w3 fluent readability table.
    """
    lc = abs(lc_value)
    # Simplified Bronze Simple Mode thresholds
    if font_size_px >= 24 and font_weight >= 300:
        return lc >= 60
    elif font_size_px >= 18.66 and font_weight >= 700:
        return lc >= 60
    else:
        return lc >= 75  # Body text default


# Example usage:
# lc = apca_contrast("#767676", "#ffffff")
# passes = apca_passes(lc, font_size_px=16, font_weight=400)
```

---

### Claude API Enrichment (`ai/enrichment.py`)

```python
import anthropic
import os
from tenacity import retry, stop_after_attempt, wait_exponential

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def enrich_page(url: str, html_snapshot: str, axe_violations: list) -> dict:
    """
    Send page HTML and axe results to Claude for contextual enrichment.
    Returns additional issues and remediation recommendations.
    """
    prompt = f"""
You are an expert accessibility auditor with CPACC qualification, auditing against WCAG 2.2 AA.

Page URL: {url}

Axe-core found these violations (already confirmed, do not duplicate):
{axe_violations}

HTML snapshot (first 8000 chars):
{html_snapshot[:8000]}

Please analyse and return a JSON object with this structure:
{{
  "additional_issues": [
    {{
      "type": "string (e.g. alt_text_quality, cognitive_load, aria_context)",
      "element": "CSS selector or description",
      "description": "Clear explanation of the issue",
      "wcag_criterion": "e.g. 1.1.1",
      "severity": "critical | major | minor",
      "recommendation": "Specific, actionable fix"
    }}
  ],
  "page_summary": "2-3 sentence plain English summary of overall accessibility status"
}}

Focus on issues automated tools miss:
- Alt text that is present but low quality, redundant, or misleading
- ARIA attributes that are technically valid but contextually wrong
- Heading structure that is technically correct but logically confusing
- Plain language issues — overly complex sentences for primary content
- Cognitive accessibility concerns — unclear labels, confusing layout patterns
- Any WCAG 2.2 specific criteria (2.4.11 Focus Not Obscured, 2.5.3 Label in Name, 3.3.7 Redundant Entry)

Return only valid JSON. No preamble or markdown.
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    import json
    return json.loads(response.content[0].text)
```

---

### Issue Data Model (`models.py`)

```python
from dataclasses import dataclass, field
from enum import Enum

class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"

@dataclass
class Issue:
    type: str                    # e.g. "missing_alt", "apca_contrast", "aria_context"
    element: str                 # CSS selector or description
    description: str
    wcag_criterion: str          # e.g. "1.4.3"
    severity: Severity
    recommendation: str
    source: str                  # "axe", "apca", "custom", "claude"

@dataclass
class PageResult:
    url: str
    issues: list[Issue] = field(default_factory=list)
    summary: str = ""

    @property
    def critical_count(self): return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)
    @property
    def major_count(self): return sum(1 for i in self.issues if i.severity == Severity.MAJOR)
    @property
    def minor_count(self): return sum(1 for i in self.issues if i.severity == Severity.MINOR)

@dataclass
class Report:
    site_url: str
    pages: list[PageResult] = field(default_factory=list)
    generated_at: str = ""
```

---

### Environment Setup (`.env.example`)

```
ANTHROPIC_API_KEY=your_key_here
DEFAULT_DELAY=1.0
DEFAULT_MAX_DEPTH=5
OUTPUT_DIR=outputs/
```

---

## 6. Agent Personas

The agent system lives in `accessibility_sweep/agent/` and implements Claude API tool use. Each persona is an independent agent run where Claude receives a system prompt, a restricted set of Playwright-backed tools, and the page context. It decides what to test, calls tools, reasons about the results, and reports findings as structured JSON.

### How the Agent Loop Works (`agent/core.py`)

1. Build structured context for the persona (page URL, axe findings, reference data)
2. Send persona system prompt + context + tool definitions to Claude (`claude-sonnet-4-20250514`)
3. Claude responds with `tool_use` blocks — execute each against the live Playwright page
4. Feed tool results back to Claude
5. Repeat until Claude produces a final JSON assessment (`stop_reason=end_turn`) or the turn limit is reached
6. Parse the JSON assessment into `Issue` objects

The loop has a safety cap of **40 tool-call round-trips** by default (60 for the journey persona). If the limit is reached, Claude is asked to provide its final assessment immediately.

API calls use `tenacity` for retry logic (3 attempts with exponential backoff). Screenshot tool results are passed as base64 image content blocks. Large tool results are truncated at 12,000 characters.

### Keyboard Navigation Persona

**File:** `agent/personas/keyboard.py`

**Identity:** A keyboard-only user who cannot use a mouse. Navigates exclusively with Tab, Shift+Tab, Enter, Space, Arrow keys, and Escape.

**Tools:** `press_key`, `get_focus_state`, `get_focusable_elements`, `get_accessibility_tree`, `get_headings`

**Excluded tools:** `click_element`, `take_screenshot` — this persona cannot click and cannot see.

**Testing procedure:**
1. Check for a skip-to-content link (Tab from top of page, activate with Enter)
2. Tab through every interactive element — check focus visibility, accessible name, role, and whether focus is obscured by sticky elements
3. Test ARIA widget keyboard patterns (modals, dropdowns, tab panels, accordions) against the ARIA Authoring Practices Guide
4. Compare recorded focus order against DOM order from `get_focusable_elements`
5. Test reverse tab order (Shift+Tab)

**WCAG criteria evaluated:** 2.1.1 Keyboard, 2.1.2 No Keyboard Trap, 2.4.1 Bypass Blocks, 2.4.3 Focus Order, 2.4.7 Focus Visible, 2.4.11 Focus Not Obscured (Minimum), 2.4.12 Focus Not Obscured (Enhanced), 3.2.1 On Focus

**Context provided:** DOM-order list of interactive elements, accessibility tree, axe findings, ARIA keyboard patterns from `reference/aria_patterns.json`

### Screen Reader Persona

**File:** `agent/personas/screen_reader.py`

**Identity:** A screen reader user who perceives the page through its accessibility tree — roles, names, states, and reading order. Cannot see the visual layout.

**Tools:** `get_accessibility_tree`, `get_page_text`, `get_element_details`, `get_live_regions`, `get_headings`, `get_landmarks`, `get_form_fields`, `press_key`

**Excluded tools:** `take_screenshot`, `click_element` — this persona cannot see and does not use a mouse.

**Testing procedure:**
1. Review page title for descriptiveness
2. Walk the accessibility tree — check every element has a meaningful name, correct role, and appropriate states
3. Evaluate heading hierarchy (single h1, logical flow, no skipped levels)
4. Check landmarks (main, navigation, labelled when duplicated)
5. Check live regions for dynamic content announcements
6. Verify form fields have programmatic labels and descriptions
7. Drill into suspicious elements for ARIA misuse
8. Test dynamic content (expand accordions, open dropdowns, re-check tree)

**WCAG criteria evaluated:** 1.1.1 Non-text Content, 1.3.1 Info and Relationships, 1.3.2 Meaningful Sequence, 2.4.2 Page Titled, 2.4.4 Link Purpose, 2.4.6 Headings and Labels, 2.5.3 Label in Name, 3.3.2 Labels or Instructions, 4.1.2 Name Role Value, 4.1.3 Status Messages

**Context provided:** Accessibility tree, heading hierarchy, landmark regions, form fields, axe findings, screen reader announcement reference from `reference/screen_reader_mappings.json`

### Cognitive Load Persona

**File:** `agent/personas/cognitive.py`

**Identity:** A user with cognitive disabilities who needs clear language, predictable interactions, simple layouts, and helpful error recovery.

**Tools:** `take_screenshot`, `get_page_metrics`, `get_page_text`, `get_form_fields`, `get_headings`, `get_error_messages`

**Excluded tools:** `press_key` (focuses on content/design, not input method), `get_accessibility_tree` (evaluates what is perceived visually)

**Testing procedure:**
1. Take a screenshot — evaluate visual hierarchy, clutter, spacing, grouping
2. Get page metrics — check Flesch-Kincaid grade level, sentence length, link density, call-to-action count, abbreviations, autoplay content
3. Read page text — identify jargon, idioms, complex vocabulary, unexpanded abbreviations
4. Check heading structure for scannability
5. If forms are present — check labels, required field marking, instructions, autocomplete attributes, error message clarity

**WCAG criteria evaluated:** 1.3.5 Identify Input Purpose, 2.2.1 Timing Adjustable, 2.4.2 Page Titled, 2.4.6 Headings and Labels, 3.1.3 Unusual Words, 3.1.4 Abbreviations, 3.1.5 Reading Level, 3.2.3 Consistent Navigation, 3.2.4 Consistent Identification, 3.2.6 Consistent Help, 3.3.1 Error Identification, 3.3.2 Labels or Instructions, 3.3.3 Error Suggestion, 3.3.4 Error Prevention, 3.3.7 Redundant Entry, 3.3.8 Accessible Authentication (Minimum), 3.3.9 Accessible Authentication (Enhanced)

**Context provided:** Page metrics, page text, form fields, headings, error messages, axe findings, screenshot

### Multi-Page Journey Persona

**File:** `agent/personas/journey.py`

**Identity:** A cross-page flow tester that navigates between pages to evaluate consistency and end-to-end accessibility.

**Tools:** All keyboard and screen reader tools plus `navigate_to`, `click_element`, `get_links`, `get_page_url`

**Testing procedure:**
1. Map the site structure by getting all links on the starting page
2. Follow 3-5 representative user journeys
3. At each page, check navigation consistency, unique page titles, skip link presence, and keyboard accessibility
4. Compare landmark and heading patterns across pages
5. Verify a user can complete key tasks across multiple pages using only keyboard and screen reader

**WCAG criteria evaluated:** 2.4.1 Bypass Blocks, 2.4.2 Page Titled, 2.4.5 Multiple Ways, 2.4.8 Location, 3.2.3 Consistent Navigation, 3.2.4 Consistent Identification, 3.3.7 Redundant Entry

**Run conditions:** The journey persona runs after all individual page scans and only when more than one URL is being scanned. It gets 60 tool-call rounds (vs 40 default) to account for multi-page navigation.

### Tool Definitions (`agent/tools.py`)

Each tool is a Playwright wrapper defined as an Anthropic tool-use JSON schema. Tools are grouped by persona:

| Tool | Keyboard | Screen Reader | Cognitive | Journey |
|---|---|---|---|---|
| `press_key` | Yes | Yes | - | Yes |
| `get_focus_state` | Yes | - | - | - |
| `get_focusable_elements` | Yes | - | - | - |
| `get_accessibility_tree` | Yes | Yes | - | Yes |
| `get_page_text` | - | Yes | Yes | Yes |
| `get_element_details` | - | Yes | - | - |
| `get_live_regions` | - | Yes | - | - |
| `get_landmarks` | - | Yes | - | - |
| `get_form_fields` | - | Yes | Yes | - |
| `get_headings` | Yes | Yes | Yes | Yes |
| `take_screenshot` | - | - | Yes | - |
| `get_page_metrics` | - | - | Yes | - |
| `get_error_messages` | - | - | Yes | - |
| `navigate_to` | - | - | - | Yes |
| `click_element` | - | - | - | Yes |
| `get_links` | - | - | - | Yes |
| `get_page_url` | - | - | - | Yes |

### Reference Data

- **`reference/aria_patterns.json`** — Maps ARIA widget roles (dialog, menu, tablist, combobox, accordion, carousel) to their expected keyboard interaction patterns. Used by the keyboard persona to know which keys to test for each widget.
- **`reference/screen_reader_mappings.json`** — Maps common HTML/ARIA combinations to what screen readers would announce (e.g. `<button>Submit</button>` → "Submit, button"). Used by the screen reader persona to judge whether elements are announced correctly.

---

## 7. What Agents and Static Analysis Each Catch

| Issue Type | axe-core / Custom | Agent Persona |
|---|---|---|
| Missing alt text | ✅ axe-core | — |
| Alt text present but wrong quality | ❌ | ✅ Screen Reader |
| Invalid ARIA attribute | ✅ axe-core | — |
| ARIA correct but contextually misleading | ❌ | ✅ Screen Reader |
| Colour contrast (WCAG 2.x ratio) | ✅ axe-core | — |
| APCA enhanced contrast | ✅ custom check | — |
| Keyboard trap | Partial | ✅ Keyboard |
| Missing skip-to-content link | ❌ | ✅ Keyboard |
| Focus indicator not visible | Partial | ✅ Keyboard |
| Focus obscured by sticky element | ❌ | ✅ Keyboard |
| Illogical tab order | ❌ | ✅ Keyboard |
| Widget keyboard patterns (ARIA APG) | ❌ | ✅ Keyboard |
| Missing accessible names | ✅ axe-core | ✅ Screen Reader (quality) |
| Landmark structure issues | ✅ custom check | ✅ Screen Reader (context) |
| Live region / status announcements | ❌ | ✅ Screen Reader |
| Label in name mismatch | ❌ | ✅ Screen Reader |
| Heading order violations | ✅ custom check | — |
| Headings logically confusing | ❌ | ✅ Screen Reader |
| Plain language / reading level | ❌ | ✅ Cognitive |
| Visual clutter / cognitive overload | ❌ | ✅ Cognitive |
| Unclear error messages | ❌ | ✅ Cognitive |
| Missing autocomplete attributes | ❌ | ✅ Cognitive |
| Abbreviations unexplained | ❌ | ✅ Cognitive |
| Inconsistent navigation across pages | ❌ | ✅ Journey |
| Non-unique page titles | ❌ | ✅ Journey |
| Cross-page keyboard flow broken | ❌ | ✅ Journey |
| Specific remediation advice with code | ❌ | ✅ All personas |

---

## 8. Installation & First Run

```bash
# Clone / create project
mkdir accessibility-sweep && cd accessibility-sweep

# Install dependencies
pip install playwright axe-playwright-python anthropic \
            beautifulsoup4 httpx jinja2 python-dotenv rich tenacity

# Install Playwright browser
playwright install chromium

# Set up env
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# Static analysis only — no AI, no tokens
python3 cli.py --url https://example.com --static-only

# Run against a single page (Phase 1)
python3 cli.py --url https://example.com --depth 0

# Run full site crawl
python3 cli.py --url https://client-site.com --depth 3 --delay 1.5

# Manual URL list
python3 cli.py --urls https://site.com/page-1 https://site.com/page-2

# Run with agent personas (requires ANTHROPIC_API_KEY)
python3 cli.py --url https://example.com --agent keyboard
python3 cli.py --url https://example.com --agent screen_reader
python3 cli.py --url https://example.com --agent cognitive
python3 cli.py --url https://example.com --agent keyboard screen_reader cognitive
python3 cli.py --url https://example.com --agent all  # all four personas including journey

# Agent personas with multi-page crawl (journey persona runs cross-page analysis)
python3 cli.py --url https://example.com --depth 3 --agent all

# Lighter AI enrichment without the full agent loop
python3 cli.py --url https://example.com --claude

# Exclude patterns and choose output format
python3 cli.py --url https://example.com --agent all --exclude "/admin/*" --format html
```

---

## 9. Extensibility

**Static checks:** Each check type lives in its own module under `scanner/` and can be added without touching the rest of the pipeline.

**Agent personas:** New personas can be added by creating a module in `agent/personas/` with a `SYSTEM_PROMPT`, a tool set from the available tools in `agent/tools.py`, and a `run()` function that calls `agent.core.run_persona()`. New Playwright-backed tools can be added to `agent/tools.py` by defining the JSON schema and implementing the execution function.

**Token budget:** Static analysis costs zero tokens and always runs. Each persona run costs roughly 5,000-15,000 input tokens and 2,000-5,000 output tokens per page, depending on complexity and step count. The `--static-only` flag skips all AI for quick sweeps.

## 10. What This Is Not

This tool is an aid, not a replacement for manual accessibility testing. It catches a significant portion of issues automatically and uses AI to evaluate things that rules cannot, but it cannot fully replicate the experience of a real screen reader user, a real keyboard user, or a real person with cognitive disabilities.

Every report includes a note: "This automated and AI-assisted audit covers approximately 60-70% of WCAG 2.2 AA criteria. A manual audit by a qualified accessibility specialist is recommended to verify findings and catch issues that require human judgement."