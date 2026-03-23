"""Terminal reporter — produces the stdout governance report.

Works without rich. If rich is installed, uses colors and formatting.
The output format exactly matches the README.md example.
"""

from __future__ import annotations

import sys
from io import StringIO

from diplomat_canary.models import ScanResult, Tool
from diplomat_canary.analyzer.scenarios import estimate_total_financial_exposure

# Try importing rich; gracefully degrade if not installed
try:
    from rich.console import Console
    from rich.text import Text
    from rich.rule import Rule
    from rich.panel import Panel

    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False

_VERDICT_ICONS = {
    "UNGUARDED": "⚠",
    "PARTIALLY_GUARDED": "⚠",
    "GUARDED": "✓",
    "LOW_RISK": "✓",
}

_VERDICT_LABELS = {
    "UNGUARDED": "❌ UNGUARDED",
    "PARTIALLY_GUARDED": "⚡ PARTIALLY GUARDED",
    "GUARDED": "✅ GUARDED",
    "LOW_RISK": "✅ LOW RISK",
}


def _format_params(tool: Tool) -> str:
    return ", ".join(p["name"] for p in tool.params) if tool.params else ""


def _plain_tool_block(tool: Tool) -> str:
    """Render a single tool block in plain text."""
    lines: list[str] = []
    icon = _VERDICT_ICONS.get(tool.verdict, "?")
    params_str = _format_params(tool)
    sig = f"{tool.name}({params_str})"
    lines.append(f"{icon} {sig}")

    if tool.verdict == "LOW_RISK":
        ro_label = "Read-only:"
        lines.append(f"  {ro_label:<24}YES")
    else:
        # Show expected guard check lines per category
        categories = list(dict.fromkeys(se.category for se in tool.side_effects))
        guard_types_present = {g.type: g for g in tool.guards}
        for cat in categories:
            expected = _CATEGORY_EXPECTED_GUARDS.get(cat, [(_category_label(cat), "")])
            for label, guard_type in expected:
                guard = guard_types_present.get(guard_type)
                if guard:
                    gv = f"{guard.type.replace('_', ' ').title()} ({guard.coverage.upper()})"
                    lines.append(f"  {label:<24}{gv}")
                else:
                    lines.append(f"  {label:<24}NONE")

        # Show matching scenarios
        if tool.verdict in ("UNGUARDED", "PARTIALLY_GUARDED"):
            for cat in categories:
                risk_hint = _category_risk_hint(cat)
                if risk_hint:
                    lines.append(f"  → Risk: {risk_hint}")

        # Show missing-check hints for UNGUARDED tools
        if tool.verdict == "UNGUARDED" and tool.missing_hints:
            lines.append("  ⤷ " + " · ".join(tool.missing_hints))

    verdict_label = _VERDICT_LABELS.get(tool.verdict, tool.verdict)
    lines.append(f"  Governance: {verdict_label}")
    return "\n".join(lines)


def _category_label(category: str) -> str:
    labels = {
        "payment": "Bounds on amount:",
        "database_write": "Write protection:",
        "database_delete": "Batch protection:",
        "http_write": "Rate limit:",
        "email": "Rate limit:",
        "publish": "Approval step:",
        "file_delete": "Confirmation step:",
        "destructive": "Confirmation step:",
    }
    return labels.get(category, f"{category}:")


# Expected guard check lines per side-effect category (matching README format)
_CATEGORY_EXPECTED_GUARDS: dict[str, list[tuple[str, str]]] = {
    "payment": [
        ("Bounds on amount:", "input_validation"),
        ("Rate limit:", "rate_limit"),
        ("Approval step:", "approval_step"),
    ],
    "database_write": [
        ("Write protection:", "input_validation"),
        ("Rate limit:", "rate_limit"),
    ],
    "database_delete": [
        ("Batch protection:", "input_validation"),
        ("Confirmation step:", "approval_step"),
    ],
    "http_write": [
        ("Rate limit:", "rate_limit"),
        ("Retry bound:", "retry_bound"),
    ],
    "email": [
        ("Rate limit:", "rate_limit"),
    ],
    "publish": [
        ("Approval step:", "approval_step"),
    ],
    "file_delete": [
        ("Confirmation step:", "approval_step"),
    ],
    "destructive": [
        ("Confirmation step:", "approval_step"),
    ],
}


def _guard_covers_category(guard_type: str, category: str) -> bool:
    """Return True if a guard type is relevant for a given side-effect category."""
    coverage_map: dict[str, set[str]] = {
        "payment": {"input_validation", "rate_limit", "approval_step", "idempotency_key"},
        "database_write": {"input_validation", "rate_limit", "auth_check", "idempotency_key"},
        "database_delete": {"input_validation", "approval_step", "auth_check", "confirmation"},
        "http_write": {"rate_limit", "retry_bound", "auth_check"},
        "email": {"rate_limit", "auth_check"},
        "publish": {"approval_step", "auth_check"},
        "file_delete": {"approval_step", "input_validation", "auth_check"},
    }
    return guard_type in coverage_map.get(category, set())


def _category_risk_hint(category: str) -> str:
    hints = {
        "payment": "agent loop could execute 200 refunds in 10 min",
        "database_delete": "single prompt could trigger mass deletion",
        "database_write": "agent loop could write 200 records unvalidated",
        "http_write": "agent could exhaust external API quota with 200 calls",
        "email": "agent could send 200 messages — spam risk",
        "publish": "agent could publish content without review",
        "file_delete": "agent could delete critical files without confirmation",
    }
    return hints.get(category, "")


# ---------------------------------------------------------------------------
# Plain text renderer
# ---------------------------------------------------------------------------


def render_plain(result: ScanResult, scanned_path: str) -> str:
    """Render the full report as plain text."""
    buf = StringIO()

    def w(line: str = "") -> None:
        buf.write(line + "\n")

    w("🐤 diplomat-canary — governance scan")
    w()
    w(f"Scanned: {scanned_path}")

    non_low_risk = [t for t in result.tools if t.verdict != "LOW_RISK"]
    w(f"Tools with side effects: {len(non_low_risk)}")
    w()

    if not result.tools:
        w("No tools with side effects detected.")
        w()
    else:
        for tool in result.tools:
            w(_plain_tool_block(tool))
            w()

    w("─" * 40)

    s = result.summary
    guarded_count = s["guarded"] + s.get("low_risk", 0)
    w(
        f"RESULT: {s['unguarded']} with no checks"
        f" · {s['partially_guarded']} with partial checks"
        f" · {guarded_count} guarded"
        f" ({s['total_tools']} total)"
    )

    exposure = estimate_total_financial_exposure(result.scenarios)
    if exposure > 0:
        w(f"Estimated exposure: ${exposure:,}/day")

    w()
    w("  Fix              → add validation in code, the next scan picks it up")
    w("  Acknowledge      → add  # checked:ok  in your source code")
    w("  Protected elsewhere → add  # checked:ok — protected by [where]")
    w("  CI enforcement   → --fail-on-unchecked blocks PRs with new unreviewed tool calls")

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Rich renderer
# ---------------------------------------------------------------------------


def _render_rich(result: ScanResult, scanned_path: str) -> None:
    """Render the report using rich formatting."""
    console = Console()

    console.print()
    console.print("[bold yellow]🐤 diplomat-canary[/bold yellow] — governance scan")
    console.print()
    console.print(f"Scanned: [cyan]{scanned_path}[/cyan]")

    non_low_risk = [t for t in result.tools if t.verdict != "LOW_RISK"]
    console.print(f"Tools with side effects: [bold]{len(non_low_risk)}[/bold]")
    console.print()

    for tool in result.tools:
        _render_rich_tool(console, tool)
        console.print()

    console.rule(style="dim")

    s = result.summary
    guarded_count = s["guarded"] + s.get("low_risk", 0)
    console.print(
        f"RESULT: [bold red]{s['unguarded']} with no checks[/bold red]"
        f" · [bold yellow]{s['partially_guarded']} with partial checks[/bold yellow]"
        f" · [bold green]{guarded_count} guarded[/bold green]"
        f" [dim]({s['total_tools']} total)[/dim]"
    )

    exposure = estimate_total_financial_exposure(result.scenarios)
    if exposure > 0:
        console.print(f"Estimated exposure: [bold red]${exposure:,}/day[/bold red]")

    console.print()
    console.print("  Fix              → add validation in code, the next scan picks it up")
    console.print("  Acknowledge      → add  [bold]# checked:ok[/bold]  in your source code")
    console.print("  Protected elsewhere → add  [bold]# checked:ok[/bold] — protected by [where]")
    console.print("  CI enforcement   → [bold]--fail-on-unchecked[/bold] blocks PRs with new unreviewed tool calls")


def _render_rich_tool(console, tool: Tool) -> None:  # type: ignore[no-untyped-def]
    params_str = _format_params(tool)
    sig = f"{tool.name}({params_str})"

    if tool.verdict == "UNGUARDED":
        icon_color = "red"
        icon = "⚠"
    elif tool.verdict == "PARTIALLY_GUARDED":
        icon_color = "yellow"
        icon = "⚠"
    else:
        icon_color = "green"
        icon = "✓"

    console.print(f"[{icon_color}]{icon}[/{icon_color}] [bold]{sig}[/bold]")

    if tool.verdict == "LOW_RISK":
        ro_label = "Read-only:"
        console.print(f"  {ro_label:<24}[green]YES[/green]")
    else:
        categories = list(dict.fromkeys(se.category for se in tool.side_effects))
        guard_types_present = {g.type: g for g in tool.guards}
        for cat in categories:
            expected = _CATEGORY_EXPECTED_GUARDS.get(cat, [(_category_label(cat), "")])
            for label, guard_type in expected:
                guard = guard_types_present.get(guard_type)
                if guard:
                    gv = f"{guard.type.replace('_', ' ').title()} ({guard.coverage.upper()})"
                    console.print(f"  {label:<24}[green]{gv}[/green]")
                else:
                    console.print(f"  {label:<24}[red]NONE[/red]")

        if tool.verdict in ("UNGUARDED", "PARTIALLY_GUARDED"):
            for cat in categories:
                hint = _category_risk_hint(cat)
                if hint:
                    console.print(f"  [dim]→ Risk: {hint}[/dim]")

        if tool.verdict == "UNGUARDED" and tool.missing_hints:
            console.print("  [dim]⤷ " + " · ".join(tool.missing_hints) + "[/dim]")

    verdict_label = _VERDICT_LABELS.get(tool.verdict, tool.verdict)
    if tool.verdict == "UNGUARDED":
        console.print(f"  Governance: [bold red]{verdict_label}[/bold red]")
    elif tool.verdict == "PARTIALLY_GUARDED":
        console.print(f"  Governance: [bold yellow]{verdict_label}[/bold yellow]")
    else:
        console.print(f"  Governance: [bold green]{verdict_label}[/bold green]")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def print_report(
    result: ScanResult,
    scanned_path: str,
    use_rich: bool | None = None,
    file=None,
) -> None:
    """Print the governance report to stdout (or a file handle).

    Args:
        result: The scan result to report on.
        scanned_path: The path that was scanned (for display).
        use_rich: Force rich on/off. If None, auto-detect.
        file: Output file handle. Defaults to sys.stdout.
    """
    if file is None:
        file = sys.stdout

    should_use_rich = _RICH_AVAILABLE if use_rich is None else (use_rich and _RICH_AVAILABLE)

    if should_use_rich and file is sys.stdout:
        _render_rich(result, scanned_path)
    else:
        output = render_plain(result, scanned_path)
        file.write(output)
