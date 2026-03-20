# Accessibility Audit Tool — Implementation Plan
**Project:** accessibility-sweep
**Stack:** Python · Playwright · axe-core · Claude API  
**Target:** WCAG 2.2 AA
**Output:** CLI-first, HTML report + JSON + plain text summary

---

## 1. Architecture Overview

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
    ├── Custom Checks (per page)
    │     ├── Colour contrast (enhanced)
    │     ├── Heading structure
    │     ├── Landmark regions
    │     ├── Focus visibility (keyboard simulation)
    │     └── ARIA context analysis
    │
    ├── Claude API Enrichment (per page)
    │     ├── Alt text quality evaluation
    │     ├── Plain language / cognitive accessibility
    │     ├── ARIA usage in context (not just validity)
    │     ├── Remediation recommendations
    │     └── Severity re-evaluation where needed
    │
    └── Report Generator
          ├── HTML report (grouped by page + severity)
          ├── JSON output (structured, for future integration)
          └── Plain text terminal summary
```

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

**Contrast checker:** The enhanced contrast algorithm is ported from the reference JS implementation — covered in Section 6.

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
│   │   └── manual.py          # Accept list of URLs
│   │
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── axe.py             # axe-core runner via Playwright
│   │   ├── apca.py            # APCA contrast implementation
│   │   ├── structure.py       # Headings, landmarks, forms
│   │   └── keyboard.py        # Focus/keyboard simulation checks
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── enrichment.py      # Claude API calls per page
│   │   └── prompts.py         # All system/user prompt templates
│   │
│   ├── reporter/
│   │   ├── __init__.py
│   │   ├── html.py            # HTML report generator
│   │   ├── json_out.py        # JSON output
│   │   ├── terminal.py        # Plain text terminal summary
│   │   └── templates/
│   │       └── report.html    # Jinja2 HTML template
│   │
│   └── models.py              # Dataclasses: Issue, PageResult, Report
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

## 6. What Claude Catches That axe-core Cannot

| Issue Type | axe-core | Claude |
|---|---|---|
| Missing alt text | ✅ | — |
| Alt text present but wrong | ❌ | ✅ |
| Invalid ARIA attribute | ✅ | — |
| ARIA correct but contextually misleading | ❌ | ✅ |
| Colour contrast (WCAG ratio) | ✅ | — |
| Enhanced contrast | ❌ | via custom check |
| Plain language / reading level | ❌ | ✅ |
| Cognitive accessibility | ❌ | ✅ |
| Heading order violations | ✅ | — |
| Headings logically confusing | ❌ | ✅ |
| Specific remediation advice | ❌ | ✅ |
| WCAG 2.2 SC 2.4.11 (Focus Not Obscured) | Partial | ✅ |

---

## 7. Installation & First Run

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

# Run against a single page (Phase 1)
python3 cli.py --url https://example.com --depth 0

# Run full site crawl (Phase 3+)
python3 cli.py --url https://client-site.com --depth 3 --delay 1.5

# Manual URL list
python3 cli.py --urls https://site.com/page-1 https://site.com/page-2
```

---

## 8. Extensibility

The tool is structured so each check type lives in its own module under `scanner/` and can be added without touching the rest of the pipeline. The Claude enrichment layer addresses cognitive accessibility and plain language concerns beyond what automated tooling can catch.