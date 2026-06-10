"""GATE 1 negative fixture: pure tool, no external calls — must NOT be OPAQUE."""
from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("pure")


@mcp.tool()
def add(a: int, b: int) -> int:
    return a + b
