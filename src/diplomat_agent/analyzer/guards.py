"""Verdict computation for scanned tools.

Assigns a governance verdict to each Tool based on its side effects and guards.
"""
from __future__ import annotations

from diplomat_agent.models import Tool


def compute_verdict(tool: Tool) -> str:
    """Compute and return the governance verdict for a tool.

    Verdicts:
        OPAQUE             — MCP client proxy (session.call_tool); effect is server-side
        LOW_RISK           — no write side effects (read-only)
        UNGUARDED          — has write side effects, zero guards
        PARTIALLY_GUARDED  — has write side effects and some guards, but not comprehensive
        GUARDED            — has write side effects and comprehensive full-coverage guards
    """
    # GATE 4 — MCP client proxies are opaque: their real effect lives on the
    # remote server and cannot be statically analyzed from this module.
    # GATE 5 — dispatcher branches whose handler could not be resolved are also opaque.
    if tool.exposure == "mcp_client" or tool.opaque_reason:
        return "OPAQUE"

    write_effects = [se for se in tool.side_effects if se.category != "read"]

    if not write_effects:
        return "LOW_RISK"

    if not tool.guards:
        return "UNGUARDED"

    full_guards = [g for g in tool.guards if g.coverage == "full"]
    partial_guards = [g for g in tool.guards if g.coverage == "partial"]

    # Count distinct guard types
    guard_types = {g.type for g in tool.guards}

    # GUARDED: at least as many full-coverage guards as write side effects,
    # covering at least 2 distinct guard types.
    if len(full_guards) >= len(write_effects) and len(guard_types) >= 2:
        return "GUARDED"

    # If there's at least one full guard, still partially guarded
    if full_guards:
        return "PARTIALLY_GUARDED"

    # Only partial guards
    if partial_guards:
        return "PARTIALLY_GUARDED"

    return "UNGUARDED"


def apply_verdicts(tools: list[Tool]) -> list[Tool]:
    """Apply verdict to each tool in-place and return the list."""
    for tool in tools:
        tool.verdict = compute_verdict(tool)
    # Compute contract_violation after verdict (it is orthogonal to verdict)
    for tool in tools:
        tool.contract_violation = _compute_contract_violation(tool)
    return tools


def _compute_contract_violation(tool: Tool) -> str:
    """Compute the contract violation flag based on declared annotations vs actual effects.

    DECLARED_READONLY_BUT_WRITES: readOnlyHint=True but ≥1 write side effect detected.
    DECLARED_NONDESTRUCTIVE_BUT_DESTRUCTIVE: destructiveHint=False but ≥1 destructive/*_delete effect.
    destructiveHint=True + UNGUARDED = corroboration, not a violation → NONE.
    """
    _DESTRUCTIVE_CATS = frozenset({"destructive", "database_delete", "file_delete"})
    write_effects = [se for se in tool.side_effects if se.category != "read"]

    if tool.readonly_hint is True and write_effects:
        return "DECLARED_READONLY_BUT_WRITES"

    if tool.destructive_hint is False:
        destructive_effects = [se for se in write_effects if se.category in _DESTRUCTIVE_CATS]
        if destructive_effects:
            return "DECLARED_NONDESTRUCTIVE_BUT_DESTRUCTIVE"

    return "NONE"


def build_summary(tools: list[Tool], file_stats: dict[str, int] | None = None) -> dict:
    """Build the summary dict from a list of tools with verdicts applied.

    Denominator invariant (GATE 4):
        unguarded % = unguarded / (unguarded + partially_guarded + guarded + low_risk)
        OPAQUE tools are EXCLUDED from that denominator — their effect is
        server-side and cannot be evaluated locally.
        total_tools = len(tools) always (opaque included, so counts stay balanced).

    Args:
        tools: List of Tool objects with verdicts already applied.
        file_stats: Optional dict with ``files_scanned`` and ``files_skipped`` counts.
    """
    total = len(tools)
    unguarded = sum(1 for t in tools if t.verdict == "UNGUARDED")
    partially = sum(1 for t in tools if t.verdict == "PARTIALLY_GUARDED")
    guarded = sum(1 for t in tools if t.verdict == "GUARDED")
    low_risk = sum(1 for t in tools if t.verdict == "LOW_RISK")
    opaque = sum(1 for t in tools if t.verdict == "OPAQUE")

    summary: dict = {
        "files_scanned": file_stats.get("files_scanned", 0) if file_stats else 0,
        "files_skipped": file_stats.get("files_skipped", 0) if file_stats else 0,
        "total_tools": total,
        "unguarded": unguarded,
        "partially_guarded": partially,
        "guarded": guarded,
        "low_risk": low_risk,
        "opaque": opaque,
    }
    return summary
