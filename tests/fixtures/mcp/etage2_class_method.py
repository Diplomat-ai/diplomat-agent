"""GATE 5 fixture: Class.method() resolves via PascalCase receiver heuristic.

The @mcp.tool calls Writer.perform(path) — a classmethod-style direct call.
The method name 'perform' carries no destructive verb signal on its own, so
only étage 2 resolution into os.remove can produce the UNGUARDED verdict.
"""
from __future__ import annotations

import os

from fastmcp import FastMCP

mcp = FastMCP("etage2-class")


class Writer:
    @classmethod
    def perform(cls, path: str) -> None:
        os.remove(path)


@mcp.tool()
def run(path: str) -> None:
    Writer.perform(path)
