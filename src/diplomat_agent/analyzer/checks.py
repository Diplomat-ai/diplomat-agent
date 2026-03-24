"""Missing-check detection for scanned tools.

Analyses a Tool's side effects, params, and guards to produce a short list of
technical facts about what governance is absent.  The hints are displayed in
the report so the developer knows exactly what to add — not a product pitch.
"""

from __future__ import annotations

from diplomat_agent.models import Tool

# Param names that strongly imply a numeric / bounded value
_NUMERIC_PARAM_NAMES: frozenset[str] = frozenset({
    "amount", "price", "quantity", "count", "total",
    "limit", "max", "size", "fee", "cost", "budget",
})

# Side-effect categories considered destructive
_DESTRUCTIVE_CATEGORIES: frozenset[str] = frozenset({
    "database_delete", "file_delete", "destructive",
})

# Side-effect categories considered payment
_PAYMENT_CATEGORIES: frozenset[str] = frozenset({"payment"})


def detect_missing_hints(tool: Tool) -> list[str]:
    """Return a list of absent check types for an UNGUARDED tool.

    Only meaningful for tools whose verdict is UNGUARDED.  Returns [] for
    all other verdicts so callers don't need to filter.

    At most 3 hints are returned (most impactful first) to avoid cluttering
    the report.
    """
    if tool.verdict != "UNGUARDED":
        return []

    write_effects = [se for se in tool.side_effects if se.category != "read"]
    if not write_effects:
        return []

    guard_types: set[str] = {g.type for g in tool.guards}
    categories: set[str] = {se.category for se in write_effects}

    hints: list[str] = []

    # 1. Numeric params with no input_validation guard
    if "input_validation" not in guard_types:
        numeric_params = [
            p["name"] for p in tool.params
            if p.get("numeric") or p["name"].lower() in _NUMERIC_PARAM_NAMES
        ]
        if numeric_params:
            hints.append(f"no bounds on {numeric_params[0]}")

    # 2. Payment effect with no idempotency key
    if _PAYMENT_CATEGORIES & categories and "idempotency_key" not in guard_types:
        hints.append("no idempotency key")

    # 3. Destructive effect with no confirmation/approval
    if _DESTRUCTIVE_CATEGORIES & categories:
        if "confirmation" not in guard_types and "approval_step" not in guard_types:
            hints.append("no confirmation step")

    # 4. Orchestrator auto-retry with no idempotency
    if tool.auto_retried:
        hints.append(f"decorated with {tool.auto_retry_decorator} — may be retried automatically")
        if "idempotency_key" not in guard_types:
            hints.append("no idempotency mechanism found")

    # 5. No rate limit
    if "rate_limit" not in guard_types:
        hints.append("no rate limit")

    # 6. No auth check
    if "auth_check" not in guard_types:
        hints.append("no auth check")

    return hints[:3]


def apply_missing_hints(tools: list[Tool]) -> list[Tool]:
    """Populate missing_hints on each tool in-place and return the list."""
    for tool in tools:
        tool.missing_hints = detect_missing_hints(tool)
    return tools
