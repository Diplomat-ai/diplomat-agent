"""GATE 2 negative fixture: variable reassigned before method call.

`r` is first assigned `Reader()` then immediately reassigned `get_writer()`.
The scanner cannot statically determine the final type of `r`, so `r.flush()`
must NOT be resolved via type tracking.
Expected verdict: OPAQUE (never UNGUARDED from type-resolution of `r`).
"""
from __future__ import annotations

import os

from fastmcp import FastMCP

mcp = FastMCP("reassigned-var")


class Reader:
    def flush(self) -> None:
        pass  # benign


def get_writer():
    return object()


@mcp.tool()
def handler(path: str) -> None:
    r = Reader()
    r = get_writer()   # reassignment — type of r is now unknown
    r.flush()
