"""MCP fixture: FastMCP server with an unguarded tool (file deletion)."""

from mcp.server.fastmcp import FastMCP
import os

mcp = FastMCP("test-server")


@mcp.tool()
def wipe(path: str) -> None:
    """Delete a file at the given path. No guard whatsoever."""
    os.remove(path)
