"""GATE 1 (Show HN) — literal type-binding inference.

list/dict/tuple literal assignments must be bound to BUILTIN_TYPES so that
their method calls (append, get, …) are not treated as unresolved effect
carriers.

Expected verdicts:
  list_with_executor  → OPAQUE  (to_thread is the unresolved carrier, NOT append)
  dict_read_only      → clean   (only dict.get() — no external calls)
  list_append_only    → clean   (list.append only — no external calls)
"""
from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("literal-binding-test")


class FakeClient:
    class container:
        @staticmethod
        def run(image: str, **kwargs) -> object:
            ...


_client = FakeClient()


# -----------------------------------------------------------------------
# list literal + to_thread — OPAQUE via to_thread, NOT via append
# -----------------------------------------------------------------------

@mcp.tool()
async def list_with_executor(image: str, ports: list) -> str:
    """port_mappings is a list literal; append on it must NOT be the opaque_reason."""
    try:
        port_mappings = []
        for p in ports:
            port_mappings.append(p)
        result = await asyncio.to_thread(
            _client.container.run,
            image,
            publish=port_mappings,
        )
        return str(result)
    except Exception as e:
        return str(e)


# -----------------------------------------------------------------------
# dict literal + .get() only — clean (no external calls)
# -----------------------------------------------------------------------

@mcp.tool()
def dict_read_only(key: str) -> str:
    """Only dict.get() on a dict literal — must stay clean."""
    defaults = {"timeout": "30", "retries": "3"}
    value = defaults.get(key, "unknown")
    return value


# -----------------------------------------------------------------------
# list literal + .append() only — clean (no external calls)
# -----------------------------------------------------------------------

@mcp.tool()
def list_append_only(items: list) -> list:
    """list.append only, no external calls — must stay clean."""
    result = []
    for item in items:
        result.append(item)
    return result
