"""JSON reporter — produces structured output for IDE agents and CI integration.

Schema contract: fields may be added (backward-compatible), but existing fields
must not be renamed or removed without a version bump.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from diplomat_agent import __version__
from diplomat_agent.models import ScanResult, Tool


def _finding(tool: Tool) -> dict:
    """Convert a Tool to the public finding schema."""
    finding: dict = {
        "function": tool.name,
        "file": tool.file,
        "line": tool.line,
        "actions": [se.evidence for se in tool.side_effects],
        "checks": [
            {"type": g.type, "detail": g.evidence}
            for g in tool.guards
        ],
        "missing": list(tool.missing_hints),
        "verdict": tool.verdict,
        "acknowledged": tool.ignored,
        # GATE 3 — contract violation (orthogonal to verdict)
        "contract_violation": tool.contract_violation,
    }
    if tool.ignored and tool.ignore_reason:
        finding["acknowledged_reason"] = tool.ignore_reason
    # Include annotation hints when present (additive, omit when None to keep output compact)
    if tool.readonly_hint is not None:
        finding["readonly_hint"] = tool.readonly_hint
    if tool.destructive_hint is not None:
        finding["destructive_hint"] = tool.destructive_hint
    return finding


def render_json(
    result: ScanResult,
    scanned_path: str,
    scan_time_ms: int | None = None,
    file_stats: dict[str, int] | None = None,
) -> str:
    """Render the scan result as a JSON string (new structured schema)."""
    summary: dict = {
        "total": result.summary.get("total_tools", len(result.tools)),
        "unguarded": result.summary.get("unguarded", 0),
        "partially_guarded": result.summary.get("partially_guarded", 0),
        "guarded": result.summary.get("guarded", 0),
        "low_risk": result.summary.get("low_risk", 0),
    }
    if file_stats and file_stats.get("mode") == "diff-only":
        summary["mode"] = "diff-only"
        summary["files_scanned"] = file_stats.get("files_scanned", 0)
        summary["files_changed"] = file_stats.get("files_changed", 0)

    if file_stats:
        unparsed = file_stats.get("files_unparsed", [])
        if unparsed:
            summary["files_unparsed_count"] = len(unparsed)
            summary["files_unparsed"] = unparsed
        dispatchers = file_stats.get("dispatcher_files", [])
        if dispatchers:
            summary["dispatcher_files_count"] = len(dispatchers)
            summary["dispatcher_files"] = dispatchers

    data: dict = {
        "version": __version__,
        "scanned_path": scanned_path,
        "summary": summary,
        "findings": [_finding(t) for t in result.tools],
    }
    if scan_time_ms is not None:
        data["scan_time_ms"] = scan_time_ms
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
