"""HTML report generator using Jinja2."""

import os
from dataclasses import asdict

from jinja2 import Environment, FileSystemLoader

from accessibility_sweep.models import Report

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def save_html(report: Report, output_dir: str) -> str:
    """Render and save the HTML report. Returns the file path."""
    os.makedirs(output_dir, exist_ok=True)

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    template = env.get_template("report.html")

    total_critical = sum(p.critical_count for p in report.pages)
    total_major = sum(p.major_count for p in report.pages)
    total_minor = sum(p.minor_count for p in report.pages)
    total_issues = sum(len(p.issues) for p in report.pages)

    # Convert dataclasses to dicts for Jinja2, rendering enum values
    report_dict = asdict(report)
    for page in report_dict.get("pages", []):
        for issue in page.get("issues", []):
            issue["severity"] = issue["severity"].value if hasattr(issue["severity"], "value") else str(issue["severity"])
    for issue in report_dict.get("site_wide_issues", []):
        issue["severity"] = issue["severity"].value if hasattr(issue["severity"], "value") else str(issue["severity"])

    html = template.render(
        report=report_dict,
        total_critical=total_critical,
        total_major=total_major,
        total_minor=total_minor,
        total_issues=total_issues,
        site_wide_issues=report_dict.get("site_wide_issues", []),
    )

    path = os.path.join(output_dir, "report.html")
    with open(path, "w") as f:
        f.write(html)

    return path
