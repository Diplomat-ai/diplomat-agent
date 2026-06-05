"""MCP fixture: low-level @server.call_tool() dispatcher.

Tests that:
- module_is_mcp is True (mcp.server import present)
- A stderr warning is emitted (per-tool resolution not supported in v1)
- exposure stays "internal" for the dispatcher function itself
  (call_tool is not in MCP_TOOL_DECORATOR_ATTRS)
"""

from mcp.server import Server
import os

server = Server("test-server-lowlevel")


@server.call_tool()
async def handle_tool(name: str, arguments: dict) -> str:
    """Low-level MCP dispatcher — single handler for all tools."""
    os.remove(arguments.get("path", ""))
    return "done"
