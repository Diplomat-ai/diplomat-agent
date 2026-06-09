from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("t")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def lookup(conn, row):
    await conn.execute("INSERT INTO audit VALUES (1)")  # contradicts read-only claim


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def safe_read(conn, key):
    return await conn.fetch("SELECT * FROM t WHERE id=$1", key)  # no writes — no violation
