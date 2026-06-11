"""GATE 5 fixture: local var = SomeClass() binding resolves via type tracking.

Inside @mcp.tool the local `w = Writer()` lets étage 2 know `w.run(path)` is
Writer.run, which deletes the file. Verdict must be UNGUARDED (not OPAQUE).
"""
from __future__ import annotations

import os

from fastmcp import FastMCP

mcp = FastMCP("etage2-local")


class Writer:
    def run(self, path: str) -> None:
        os.remove(path)


@mcp.tool()
def handler(path: str) -> None:
    w = Writer()
    w.run(path)
