"""accessibility-sweep — CLI entry point."""

import argparse
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from rich.console import Console

from accessibility_sweep.crawler.auto import AutoCrawler
from accessibility_sweep.crawler.manual import ManualCrawler
from accessibility_sweep.scanner.axe import AxeScanner
from accessibility_sweep.scanner.apca import check_apca_contrast
from accessibility_sweep.scanner.structure import run_structure_checks
from accessibility_sweep.scanner.keyboard import check_focus_visibility
from accessibility_sweep.scanner.element_context import enrich_issues_with_context
from accessibility_sweep.models import Report, PageResult
from accessibility_sweep.analyzer import extract_site_wide_issues
from accessibility_sweep import wcag_lookup
from accessibility_sweep.reporter.terminal import print_summary
from accessibility_sweep.reporter.json_out import save_json
from accessibility_sweep.reporter.html import save_html

load_dotenv()
console = Console()


def main():
    parser = argparse.ArgumentParser(
        prog="accessibility-sweep",
        description="Accessibility auditor — WCAG 2.2 AA + Claude AI enrichment",
    )
    parser.add_argument("--url", help="Seed URL to auto-crawl from")
    parser.add_argument("--urls", nargs="+", help="Manual list of URLs to scan")
    parser.add_argument("--output", default=os.environ.get("OUTPUT_DIR", "outputs/"), help="Output directory")
    parser.add_argument("--depth", type=int, default=int(os.environ.get("DEFAULT_MAX_DEPTH", "5")), help="Max crawl depth")
    parser.add_argument("--delay", type=float, default=float(os.environ.get("DEFAULT_DELAY", "1.0")), help="Delay between pages (seconds)")
    parser.add_argument("--exclude", nargs="*", default=[], help="URL patterns to exclude")
    parser.add_argument("--claude", action="store_true", help="Enable Claude AI enrichment (requires ANTHROPIC_API_KEY)")
    parser.add_argument("--format", choices=["all", "html", "json", "terminal"], default="all", help="Output format")
    args = parser.parse_args()

    # Resolve URLs
    if args.urls:
        urls = ManualCrawler(args.urls).crawl()
    elif args.url:
        console.print(f"[bold blue]Crawling from seed:[/bold blue] {args.url}")
        crawler = AutoCrawler(args.url, max_depth=args.depth, delay=args.delay)
        urls = crawler.crawl()
    else:
        parser.error("Provide either --url or --urls")

    # Apply exclusions
    if args.exclude:
        urls = [u for u in urls if not any(pattern in u for pattern in args.exclude)]

    if not urls:
        console.print("[red]No URLs to scan.[/red]")
        sys.exit(1)

    console.print(f"\n[bold]Scanning {len(urls)} page(s)...[/bold]\n")

    # Scan each URL
    report = Report(
        site_url=args.url or urls[0],
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    axe_scanner = AxeScanner()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        for i, url in enumerate(urls, 1):
            console.print(f"[bold]  [{i}/{len(urls)}][/bold] {url}")

            try:
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)  # Allow JS to render

                # Phase 1: axe-core scan
                page_result, html = axe_scanner.scan_page(page, url)
                console.print(f"    axe-core: {len(page_result.issues)} violations")

                # Phase 2: Custom checks
                structure_issues = run_structure_checks(html)
                page_result.issues.extend(structure_issues)
                console.print(f"    structure: {len(structure_issues)} issues")

                apca_issues = check_apca_contrast(page)
                page_result.issues.extend(apca_issues)
                console.print(f"    contrast: {len(apca_issues)} issues")

                focus_issues = check_focus_visibility(page)
                page_result.issues.extend(focus_issues)
                console.print(f"    focus/keyboard: {len(focus_issues)} issues")

                # Phase 4: Claude AI enrichment (opt-in with --claude)
                if args.claude and os.environ.get("ANTHROPIC_API_KEY"):
                    try:
                        from accessibility_sweep.ai.enrichment import enrich_page
                        axe_violations = [
                            {"type": iss.type, "description": iss.description}
                            for iss in page_result.issues if iss.source == "axe"
                        ]
                        ai_issues, summary = enrich_page(url, html, axe_violations)
                        page_result.issues.extend(ai_issues)
                        page_result.summary = summary
                        console.print(f"    Claude AI: {len(ai_issues)} additional issues")
                    except Exception as e:
                        console.print(f"    [yellow]Claude AI skipped: {e}[/yellow]")
                elif args.claude:
                    console.print("    [yellow]Claude AI requested but ANTHROPIC_API_KEY not set[/yellow]")

                # Enrich all issues with WCAG 2.2 metadata
                for issue in page_result.issues:
                    wcag_lookup.enrich_issue(issue)

                # Phase 5: Resolve friendly element descriptions and page locations
                enrich_issues_with_context(page, page_result.issues)

                page.close()
                report.pages.append(page_result)

            except Exception as e:
                console.print(f"    [red]Error scanning {url}: {e}[/red]")
                report.pages.append(PageResult(url=url, summary=f"Error: {e}"))

        browser.close()

    # Phase 5: Site-wide deduplication
    extract_site_wide_issues(report)
    for issue in report.site_wide_issues:
        wcag_lookup.enrich_issue(issue)
    if report.site_wide_issues:
        console.print(
            f"\n[bold]Detected {len(report.site_wide_issues)} site-wide issue(s) "
            f"across {len(report.pages)} pages[/bold]"
        )

    # Phase 6: Report generation
    if args.format in ("all", "terminal"):
        print_summary(report)

    if args.format in ("all", "json"):
        json_path = save_json(report, args.output)
        console.print(f"[green]JSON report saved:[/green] {json_path}")

    if args.format in ("all", "html"):
        html_path = save_html(report, args.output)
        console.print(f"[green]HTML report saved:[/green] {html_path}")

    console.print("\n[bold green]Done.[/bold green]")


if __name__ == "__main__":
    main()
