"""Golden table GATE 3 fixture: mcp_client proxy — session.call_tool() → OPAQUE.

The module imports from mcp.client, making it an mcp_client module.
A function that calls session.call_tool(...) is an OPAQUE proxy.
"""
from __future__ import annotations

from mcp.client.stdio import stdio_client
from mcp import ClientSession


async def proxy_call(tool_name: str, args: dict) -> dict:
    """Calls session.call_tool — mcp_client proxy → OPAQUE."""
    async with stdio_client() as (read, write):
        async with ClientSession(read, write) as session:
            result = await session.call_tool(tool_name, args)
            return result
