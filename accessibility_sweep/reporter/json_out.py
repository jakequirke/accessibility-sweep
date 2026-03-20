"""JSON report output."""

import json
import os
from dataclasses import asdict
from enum import Enum

from accessibility_sweep.models import Report


def _serialize(obj):
    """Custom default serializer — render enums as their value."""
    if isinstance(obj, Enum):
        return obj.value
    return str(obj)


def save_json(report: Report, output_dir: str) -> str:
    """Save the full report as JSON. Returns the file path."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "report.json")

    data = asdict(report)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=_serialize)

    return path
