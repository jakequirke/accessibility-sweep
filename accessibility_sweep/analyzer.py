"""Site-wide issue deduplication and analysis."""

from collections import defaultdict

from accessibility_sweep.models import Issue, Report


def _fingerprint(issue: Issue) -> tuple[str, str, str]:
    """Create a deduplication key from an issue's stable fields."""
    return (issue.type, issue.element, issue.source)


def extract_site_wide_issues(report: Report, threshold: float = 0.5) -> None:
    """Detect issues repeated across many pages and deduplicate them.

    An issue is considered site-wide if it appears on >= threshold fraction
    of pages OR on >= 3 pages (whichever is lower). Matching issues are
    removed from per-page results and collected into report.site_wide_issues.

    Mutates *report* in place.
    """
    total_pages = len(report.pages)
    if total_pages < 2:
        return

    min_pages = min(3, max(1, int(total_pages * threshold)))

    # Map fingerprint -> list of (page_url, issue)
    fingerprint_hits: dict[tuple, list[tuple[str, Issue]]] = defaultdict(list)

    for page in report.pages:
        seen_on_page: set[tuple] = set()
        for issue in page.issues:
            fp = _fingerprint(issue)
            if fp not in seen_on_page:
                fingerprint_hits[fp].append((page.url, issue))
                seen_on_page.add(fp)

    # Identify site-wide fingerprints
    site_wide_fps: dict[tuple, list[str]] = {}
    for fp, hits in fingerprint_hits.items():
        if len(hits) >= min_pages:
            site_wide_fps[fp] = [url for url, _ in hits]

    if not site_wide_fps:
        return

    # Build site-wide issue list (one representative per fingerprint)
    for fp, page_urls in site_wide_fps.items():
        # Use the first occurrence as the representative
        representative = fingerprint_hits[fp][0][1]
        site_wide_issue = Issue(
            type=representative.type,
            element=representative.element,
            description=representative.description,
            wcag_criterion=representative.wcag_criterion,
            severity=representative.severity,
            recommendation=representative.recommendation,
            source=representative.source,
            affected_pages=page_urls,
        )
        report.site_wide_issues.append(site_wide_issue)

    # Remove site-wide issues from per-page results
    for page in report.pages:
        page.issues = [
            issue for issue in page.issues
            if _fingerprint(issue) not in site_wide_fps
        ]
