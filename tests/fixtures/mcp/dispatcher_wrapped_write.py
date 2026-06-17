"""GATE 1 fixtures — dispatcher handler with write / empty / read-only body.

The module is an MCP server (low-level call_tool API). The dispatcher routes
keys to plain Python functions that are NOT decorated with @mcp.tool.

Expected verdicts after v0.5.3 GATE 1 fix:
  commit  → OPAQUE   (has unresolved effect: repo.index.commit — treat_as_mcp_tool)
  noop    → LOW_RISK (body is a pure literal return — no carrier)
  read    → not UNGUARDED (body is a head-commit attribute read — can be LOW_RISK or OPAQUE)
"""
from __future__ import annotations

from mcp.server import Server

server = Server("git-test")


# --------------------------------------------------------------------------
# Handler functions — no @mcp.tool decorator; resolved by dispatcher below.
# --------------------------------------------------------------------------

def _commit(repo, msg="update"):
    """Calls repo.index.commit — an unresolved attribute effect-carrier."""
    repo.index.add(["*"])
    repo.index.commit(msg)
    return {"committed": True}


def _noop():
    """Pure return literal — no calls at all."""
    return {"ok": True}


def _read(repo):
    """Reads repo.head.commit.hexsha — pure attribute traversal."""
    return repo.head.commit.hexsha


# --------------------------------------------------------------------------
# Dispatcher (low-level MCP call_tool pattern)
# --------------------------------------------------------------------------

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    if name == "commit":
        return _commit(arguments.get("repo"), arguments.get("msg", "update"))
    elif name == "noop":
        return _noop()
    elif name == "read":
        return _read(arguments.get("repo"))
    return {"error": f"unknown tool: {name}"}
