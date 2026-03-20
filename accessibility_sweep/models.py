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
    affected_pages: list[str] = field(default_factory=list)  # only for site-wide issues
    wcag_name: str = ""          # e.g. "Non-text Content"
    wcag_level: str = ""         # e.g. "A", "AA", "AAA"
    visual_location: str = ""   # e.g. "Top navigation bar, right side"
    element_description: str = ""  # Human-friendly label, e.g. "Navigation link in header"
    bounding_box: dict = field(default_factory=dict)  # {"x": ..., "y": ..., "width": ..., "height": ...}


@dataclass
class PageResult:
    url: str
    issues: list[Issue] = field(default_factory=list)
    summary: str = ""

    @property
    def critical_count(self):
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    @property
    def major_count(self):
        return sum(1 for i in self.issues if i.severity == Severity.MAJOR)

    @property
    def minor_count(self):
        return sum(1 for i in self.issues if i.severity == Severity.MINOR)


@dataclass
class Report:
    site_url: str
    pages: list[PageResult] = field(default_factory=list)
    generated_at: str = ""
    site_wide_issues: list[Issue] = field(default_factory=list)
