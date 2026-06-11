"""GATE 1 fixture: wrapped DB driver — effect-carrier behind unresolved wrapper.

The @mcp.tool calls self.driver.vault_action(sql) which is not in the SDK
verb breadth and cannot be resolved by interproc. Expected verdict: OPAQUE.
"""
from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("wrapped-db")


class DbTool:
    def __init__(self, driver) -> None:
        self.driver = driver

    @mcp.tool()
    async def run_query(self, sql: str) -> list:
        return await self.driver.vault_action(sql)
