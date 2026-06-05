# MCP tools that import the server instance from a sibling module.
# This tests FIX 3: cross-module MCP gate.
import os
from .server import mcp


@mcp.tool()
def wipe_path(path: str) -> str:
    """Delete a file — should be detected as UNGUARDED mcp_tool."""
    os.remove(path)
    return path


@mcp.tool()
def read_info(path: str) -> str:
    """Read a file — reader prefix, should NOT fire as http_write."""
    return open(path).read()
