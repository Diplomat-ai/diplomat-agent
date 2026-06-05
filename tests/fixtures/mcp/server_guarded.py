"""MCP fixture: FastMCP server with a guarded tool (numeric bounds validation)."""

from mcp.server.fastmcp import FastMCP
import sqlite3

mcp = FastMCP("test-server")


@mcp.tool()
def delete_old_records(max_age_days: int) -> int:
    """Delete database records older than max_age_days. Guarded by bounds validation."""
    if max_age_days < 1 or max_age_days > 365:
        raise ValueError("max_age_days must be between 1 and 365")
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM records WHERE age > ?", (max_age_days,))
    conn.commit()
    return cursor.rowcount
