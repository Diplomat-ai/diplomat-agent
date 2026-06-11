"""GATE 5 fixture: self.method() resolves to enclosing class method.

The @mcp.tool calls self._do_write(...) which is a method on the same class.
Étage 2 must resolve it via lookup_class_method and surface os.remove as the
real side effect — verdict UNGUARDED (not OPAQUE).
"""
from __future__ import annotations

import os

from fastmcp import FastMCP

mcp = FastMCP("etage2-self")


class Writer:
    @mcp.tool()
    def run(self, path: str) -> None:
        self._do_write(path)

    def _do_write(self, path: str) -> None:
        os.remove(path)
