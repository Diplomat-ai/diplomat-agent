"""JSON reporter — produces structured output for CI integration."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from diplomat.models import ScanResult


def render_json(result: ScanResult, scanned_path: str) -> str:
    """Render the scan result as a JSON string."""
    data: dict = {
        "scanned_path": scanned_path,
        "summary": result.summary,
        "tools": [asdict(t) for t in result.tools],
        "scenarios": [asdict(s) for s in result.scenarios],
    }
    return json.dumps(data, indent=2)


def write_json_report(
    result: ScanResult,
    scanned_path: str,
    output_path: Path | None = None,
) -> Path:
    """Write the JSON report to disk and return the file path."""
    if output_path is None:
        output_path = Path("diplomat-report.json")

    content = render_json(result, scanned_path)
    output_path.write_text(content, encoding="utf-8")
    return output_path
