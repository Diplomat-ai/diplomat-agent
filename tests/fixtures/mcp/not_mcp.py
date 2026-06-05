"""MCP fixture: @something.tool decorator WITHOUT any MCP import.

Tests the import gate: a @x.tool decorator in a non-MCP module must NOT
be tagged as exposure="mcp_tool".
"""

import os


class _Registry:
    def tool(self, fn):
        return fn


something = _Registry()


@something.tool
def remove_stuff(path: str) -> None:
    """Not an MCP tool — no MCP import present, gate must block tagging."""
    os.remove(path)
