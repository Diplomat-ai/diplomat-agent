"""Markdown reporter — produces canary-report.md."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from diplomat_canary.models import ScanResult, Tool
from diplomat_canary.analyzer.scenarios import estimate_total_financial_exposure
from diplomat_canary.reporter.terminal import (
    _category_label,
    _category_risk_hint,
    _format_params,
    _guard_covers_category,
    _VERDICT_LABELS,
)

_VERDICT_MD_BADGE = {
    "UNGUARDED": "🔴 UNGUARDED",
    "PARTIALLY_GUARDED": "🟡 PARTIALLY GUARDED",
    "GUARDED": "🟢 GUARDED",
    "LOW_RISK": "🟢 LOW RISK",
}


def render_markdown(result: ScanResult, scanned_path: str) -> str:
    """Render the full report as a Markdown string."""
    lines: list[str] = []

    lines.append("# 🐤 diplomat-canary — Governance Report")
    lines.append("")
    lines.append(f"**Scanned:** `{scanned_path}`  ")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ")
    lines.append("")

    # --- Summary table ---
    s = result.summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Verdict | Count |")
    lines.append("|---------|-------|")
    lines.append(f"| 🔴 Unguarded | {s['unguarded']} |")
    lines.append(f"| 🟡 Partially Guarded | {s['partially_guarded']} |")
    lines.append(f"| 🟢 Guarded | {s['guarded']} |")
    lines.append(f"| 🟢 Low Risk | {s['low_risk']} |")
    lines.append(f"| **Total** | **{s['total_tools']}** |")
    lines.append("")

    exposure = estimate_total_financial_exposure(result.scenarios)
    if exposure > 0:
        lines.append(f"**Estimated financial exposure:** ${exposure:,}/day")
        lines.append("")

    # --- Per-tool sections ---
    lines.append("## Tool Details")
    lines.append("")

    for tool in result.tools:
        lines.extend(_tool_section(tool))
        lines.append("")

    # --- Scenarios ---
    if result.scenarios:
        lines.append("## Risk Scenarios")
        lines.append("")
        for scenario in result.scenarios:
            lines.append(f"### {scenario.tool_name}")
            lines.append(f"- **Risk category:** {scenario.risk_category}")
            lines.append(f"- **Description:** {scenario.description}")
            lines.append(f"- **Estimated impact:** {scenario.estimated_impact}")
            lines.append("")

    s = result.summary
    guarded_count = s["guarded"] + s.get("low_risk", 0)
    lines.append(
        f"**Result:** {s['unguarded']} with no checks"
        f" · {s['partially_guarded']} with partial checks"
        f" · {guarded_count} guarded"
        f" ({s['total_tools']} total)"
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    if result.summary.get("unguarded", 0) > 0:
        lines.append(
            "🔒 *Intercept these tool calls before execution → [diplomat.run](https://diplomat.run)*"
        )
        lines.append("")

    return "\n".join(lines) + "\n"


def _tool_section(tool: Tool) -> list[str]:
    lines: list[str] = []
    params_str = _format_params(tool)
    sig = f"`{tool.name}({params_str})`"
    badge = _VERDICT_MD_BADGE.get(tool.verdict, tool.verdict)
    lines.append(f"### {sig} — {badge}")
    lines.append("")
    lines.append(f"**File:** `{tool.file}:{tool.line}`")
    lines.append("")

    if tool.side_effects:
        lines.append("**Side effects detected:**")
        lines.append("")
        for se in tool.side_effects:
            lines.append(f"- `{se.category}` — `{se.evidence}` (line {se.line})")
        lines.append("")

    if tool.guards:
        lines.append("**Guards detected:**")
        lines.append("")
        for g in tool.guards:
            lines.append(
                f"- `{g.type}` ({g.coverage}) — `{g.evidence}`"
            )
        lines.append("")
    elif tool.verdict not in ("LOW_RISK",):
        lines.append("**Guards detected:** none")
        lines.append("")
        if tool.verdict == "UNGUARDED" and tool.missing_hints:
            lines.append("> ⤷ " + " · ".join(tool.missing_hints))
            lines.append("")

    return lines


def write_markdown_report(
    result: ScanResult,
    scanned_path: str,
    output_path: Path | None = None,
) -> Path:
    """Write the markdown report to disk and return the file path."""
    if output_path is None:
        output_path = Path("canary-report.md")

    content = render_markdown(result, scanned_path)
    output_path.write_text(content, encoding="utf-8")
    return output_path
