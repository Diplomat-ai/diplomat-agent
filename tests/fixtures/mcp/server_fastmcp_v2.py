"""MCP fixture: FastMCP v2 standalone import (jlowin/PrefectHQ)."""

from fastmcp import FastMCP
import os

mcp = FastMCP("test-server-v2")


@mcp.tool()
def remove_entry(path: str) -> None:
    """Remove an entry — uses standalone fastmcp import."""
    os.remove(path)
