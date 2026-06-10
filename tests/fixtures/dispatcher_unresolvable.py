"""GATE 5 fixture: dispatcher branch calling a handler not in the scan unit.

  handle_tools  — @server.call_tool dispatcher (must NOT appear as a Tool)
  "remote-op"   — handler imported from third_party_lib (not indexed) → OPAQUE
"""
from __future__ import annotations

from mcp.server import Server

server = Server("test")

# ThirdPartyHandlers is NOT importable at analysis time; PackageIndex cannot index it.
# _resolve_handler_callable returns (None, ...) → opaque_reason is set → OPAQUE verdict.
try:
    from third_party_lib import ThirdPartyHandlers  # type: ignore[import]
except ImportError:
    ThirdPartyHandlers = None  # type: ignore[assignment,misc]


@server.call_tool()
async def handle_tools(name: str, arguments: dict) -> list:
    if name == "remote-op":
        return await ThirdPartyHandlers.execute(arguments)  # type: ignore[union-attr]
