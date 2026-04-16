"""Rich terminal output for accessibility report."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from accessibility_sweep.models import Report, Severity

console = Console()

SEVERITY_COLORS = {
    Severity.CRITICAL: "bold red",
    Severity.MAJOR: "yellow",
    Severity.MINOR: "dim",
}


def print_summary(report: Report) -> None:
    """Print a formatted accessibility report to the terminal."""
    total_issues = sum(len(p.issues) for p in report.pages)
    total_critical = sum(p.critical_count for p in report.pages)
    total_major = sum(p.major_count for p in report.pages)
    total_minor = sum(p.minor_count for p in report.pages)

    # Header
    console.print()
    console.print(Panel(
        f"[bold]accessibility-sweep[/bold] — Accessibility Report\n"
        f"Site: {report.site_url}\n"
        f"Pages scanned: {len(report.pages)}\n"
        f"Generated: {report.generated_at}",
        border_style="blue",
    ))

    # Summary counts
    summary = Text()
    summary.append(f"  {total_critical} critical", style="bold red")
    summary.append(f"  {total_major} major", style="yellow")
    summary.append(f"  {total_minor} minor", style="dim")
    summary.append(f"  ({total_issues} total)")
    console.print(summary)
    console.print()

    # Site-wide issues
    if report.site_wide_issues:
        console.print(Panel(
            f"[bold]{len(report.site_wide_issues)} Site-Wide Issues[/bold] "
            f"(removed from per-page results)",
            border_style="magenta",
        ))

        sw_table = Table(show_header=True, header_style="bold", padding=(0, 1))
        sw_table.add_column("Severity", width=10)
        sw_table.add_column("Type", width=24)
        sw_table.add_column("Element", width=30)
        sw_table.add_column("Description", ratio=1)
        sw_table.add_column("Pages", width=8, justify="right")

        for issue in sorted(report.site_wide_issues, key=lambda i: list(Severity).index(i.severity)):
            style = SEVERITY_COLORS.get(issue.severity, "")
            el_label = issue.element_description or issue.element
            if issue.visual_location:
                el_label += f"\n[dim]{issue.visual_location}[/dim]"
            sw_table.add_row(
                Text(issue.severity.value.upper(), style=style),
                issue.type,
                el_label[:50],
                issue.description[:80],
                str(len(issue.affected_pages)),
            )

        console.print(sw_table)
        console.print()

    # Per-page results
    for page_result in report.pages:
        if not page_result.issues:
            console.print(f"[green]  {page_result.url} — No issues found[/green]")
            continue

        console.print(f"[bold]  {page_result.url}[/bold]")

        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("Severity", width=10)
        table.add_column("Type", width=24)
        table.add_column("Element", width=30)
        table.add_column("Description", ratio=1)

        for issue in sorted(page_result.issues, key=lambda i: list(Severity).index(i.severity)):
            style = SEVERITY_COLORS.get(issue.severity, "")
            el_label = issue.element_description or issue.element
            if issue.visual_location:
                el_label += f"\n[dim]{issue.visual_location}[/dim]"
            table.add_row(
                Text(issue.severity.value.upper(), style=style),
                issue.type,
                el_label[:50],
                issue.description[:80],
            )

        console.print(table)

        if page_result.summary:
            console.print(f"  [dim]{page_result.summary}[/dim]")
        console.print()

    # Footer
    console.print(Panel(
        f"Scan complete. {total_issues} issues found across {len(report.pages)} pages.",
        border_style="blue",
    ))

    # Disclaimer
    console.print()
    console.print(Panel(
        "[dim]This automated and AI-assisted audit covers approximately 60-70% of "
        "WCAG 2.2 AA criteria. A manual audit by a qualified accessibility specialist "
        "is recommended to verify findings and catch issues that require human "
        "judgement.[/dim]",
        title="[dim]Disclaimer[/dim]",
        border_style="dim",
    ))
