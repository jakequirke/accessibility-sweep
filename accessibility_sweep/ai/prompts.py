"""Prompt templates for Claude API enrichment."""

SYSTEM_PROMPT = (
    "You are a senior accessibility auditor with CPACC and IAAP WAS certification, "
    "specialising in WCAG 2.2 AA compliance audits for commercial websites. "
    "You provide detailed, evidence-based analysis with specific references to "
    "WCAG success criteria and practical remediation guidance. "
    "You return only valid JSON — no preamble, markdown, or commentary outside the JSON."
)

PAGE_ANALYSIS_PROMPT = """\
Page URL: {url}

Axe-core already found these violations (confirmed — do NOT duplicate or re-report these):
{axe_violations}

HTML snapshot (first 12000 chars):
{html_snapshot}

Perform a thorough contextual accessibility analysis of this page. Return a JSON object with this exact structure:
{{
  "additional_issues": [
    {{
      "type": "string — one of: alt_text_quality, cognitive_load, aria_context, plain_language, focus_management, label_in_name, heading_structure, redundant_entry, target_size, reading_order, sensory_characteristics, status_messages, link_purpose, form_instructions, error_identification, consistent_navigation, page_titled",
      "element": "CSS selector identifying the element (be as specific as possible)",
      "visual_location": "Describe where on the visible page this element appears — e.g. 'Hero banner, centre of page above the fold', 'Footer section, bottom-left newsletter signup form', 'Main navigation bar, top-right corner'. Be specific about the section/area and position so a sighted reviewer can locate it immediately.",
      "description": "Detailed explanation of the issue (3-5 sentences minimum). Explain: (1) what the current state of the element is, (2) why this is an accessibility barrier and who it affects (screen reader users, keyboard users, cognitive disabilities, low vision, etc.), (3) what WCAG success criterion it violates and why.",
      "wcag_criterion": "e.g. 1.1.1",
      "severity": "critical | major | minor",
      "recommendation": "Specific, actionable remediation with code examples where helpful. Include the exact HTML/ARIA changes needed. If multiple approaches exist, recommend the best one and briefly note alternatives."
    }}
  ],
  "page_summary": "4-6 sentence comprehensive summary of the page's overall accessibility posture. Cover: (1) the most impactful barriers, (2) which user groups are most affected, (3) any positive accessibility features already present, (4) priority order for remediation."
}}

Analyse THOROUGHLY for issues that automated tools like axe-core cannot detect:

**Content & semantics:**
- Alt text that exists but is low quality, generic (e.g. "image", "photo"), redundant with adjacent text, or misleading about the image content
- Decorative images incorrectly given alt text (should be alt="" or role="presentation")
- Heading hierarchy that is technically valid but logically confusing or doesn't reflect the visual structure
- Reading order in the DOM that doesn't match visual presentation
- Link text that is vague or duplicated (multiple "Read more", "Click here" without context)
- Page title that doesn't describe the page purpose

**ARIA & interactive patterns:**
- ARIA attributes that are technically valid but contextually wrong (e.g. aria-label that contradicts visible text)
- Missing or incorrect ARIA roles on custom interactive components
- Live regions that should announce dynamic content changes but don't
- Modal dialogs that don't trap focus or return focus on close
- Custom widgets missing required ARIA properties (e.g. sliders without aria-valuenow)

**Cognitive accessibility:**
- Content that uses unnecessarily complex language where simpler alternatives exist
- Unclear or ambiguous form labels and instructions
- Error messages that don't explain what went wrong or how to fix it
- Inconsistent navigation or identification patterns
- Information conveyed only through colour, shape, or sensory characteristics
- Cognitive overload from too many choices without clear hierarchy

**Keyboard & focus:**
- Focus order that doesn't follow logical reading sequence
- Interactive elements that may not be keyboard accessible (divs/spans used as buttons)
- Keyboard traps or unexpected focus behaviour

**WCAG 2.2 specific criteria:**
- 2.4.11 Focus Not Obscured — is the focused element ever hidden behind sticky headers/footers/modals?
- 2.5.8 Target Size (Minimum) — interactive targets smaller than 24x24 CSS pixels without sufficient spacing
- 2.4.13 Focus Appearance — focus indicators that don't meet the minimum area/contrast requirements
- 3.3.7 Redundant Entry — users asked to re-enter information already provided in the same session
- 3.3.8 Accessible Authentication — authentication that relies on cognitive function tests

Be thorough. Report every genuine issue you find. Provide enough detail that a developer can understand AND fix each issue without further research.

Return only valid JSON. No preamble or markdown.
"""
