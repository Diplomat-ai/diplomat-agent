"""Fixture: MCP client module — GATE 4 (OPAQUE / external_mcp_call).

module_is_mcp_client = True  (imports mcp.client.streamable_http)
module_is_mcp        = False (no mcp.server import)

call_remote_tool  → session.call_tool() → exposure mcp_client, verdict OPAQUE
call_remote_named → client.call_tool()  → exposure mcp_client, verdict OPAQUE
innocent_helper   → no call_tool        → never returned by scan_file
"""
from __future__ import annotations

import mcp.client.streamable_http  # noqa: F401 — triggers module_is_mcp_client gate


async def call_remote_tool(name: str, arguments: dict, session) -> dict:
    """Proxy to a remote MCP server tool — effect is server-side, locally opaque."""
    result = await session.call_tool(name, arguments)
    return result


async def call_remote_named(client, tool_name: str, params: dict) -> dict:
    """Same pattern with receiver named 'client' instead of 'session'."""
    return await client.call_tool(tool_name, params)


async def innocent_helper(x: int) -> int:
    """No call_tool and no local side effects — must NOT appear in scan output."""
    return x + 1
