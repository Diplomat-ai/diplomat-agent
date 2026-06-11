"""GATE 1 negative fixture: @mcp.tool with only stdlib method calls on typed params.

All method calls here are on receivers whose type is a known builtin (str, dict,
list). None are external side effects. Expected verdict: NOT OPAQUE (dropped or
LOW_RISK — no genuine effect carrier present).
"""
from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("benign-typed")


@mcp.tool()
def fmt(s: str, d: dict, items: list) -> str:
    return s.upper() + str(d.get("k")) + str(items[:2])
