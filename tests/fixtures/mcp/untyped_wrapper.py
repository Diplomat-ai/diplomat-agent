"""GATE 2 negative fixture: @mcp.tool with untyped driver parameter.

`driver` has NO type annotation. The method `do_custom(sql)` is not a
recognised SDK verb and cannot be resolved by étage-2 type tracking.
Expected verdict: OPAQUE (never UNGUARDED — we must not guess the type).
"""
from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("untyped-wrapper")


@mcp.tool()
def t(driver, sql):
    return driver.do_custom(sql)
