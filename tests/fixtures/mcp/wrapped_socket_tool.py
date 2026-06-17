"""GATE 1 fixture: wrapped socket — effect-carrier behind unresolved wrapper.

The @mcp.tool calls conn.vault_transfer(...) which masks a TCP socket write.
Expected verdict: OPAQUE.
"""
from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("wrapped-socket")


class SocketTool:
    def __init__(self, conn) -> None:
        self.conn = conn

    @mcp.tool()
    def do_thing(self, payload: dict) -> dict:
        return self.conn.vault_transfer("execute_code", {"payload": payload})
