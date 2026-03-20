"""Claude API enrichment — contextual accessibility analysis per page."""

import json
import os

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from accessibility_sweep.ai.prompts import SYSTEM_PROMPT, PAGE_ANALYSIS_PROMPT
from accessibility_sweep.models import Issue, Severity

SEVERITY_MAP = {
    "critical": Severity.CRITICAL,
    "major": Severity.MAJOR,
    "minor": Severity.MINOR,
}


def _get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to your .env file or export it."
        )
    return anthropic.Anthropic(api_key=api_key)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def enrich_page(url: str, html_snapshot: str, axe_violations: list[dict]) -> tuple[list[Issue], str]:
    """
    Send page HTML and axe results to Claude for contextual enrichment.
    Returns (additional_issues, page_summary).
    """
    client = _get_client()

    prompt = PAGE_ANALYSIS_PROMPT.format(
        url=url,
        axe_violations=json.dumps(axe_violations, indent=2)[:4000],
        html_snapshot=html_snapshot[:12000],
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    data = json.loads(response.content[0].text)

    issues = []
    for item in data.get("additional_issues", []):
        issues.append(Issue(
            type=item.get("type", "claude_finding"),
            element=item.get("element", ""),
            description=item.get("description", ""),
            wcag_criterion=item.get("wcag_criterion", ""),
            severity=SEVERITY_MAP.get(item.get("severity", "minor"), Severity.MINOR),
            recommendation=item.get("recommendation", ""),
            source="claude",
            visual_location=item.get("visual_location", ""),
        ))

    summary = data.get("page_summary", "")
    return issues, summary
