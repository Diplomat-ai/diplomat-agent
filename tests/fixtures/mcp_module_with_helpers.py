"""GATE 6 fixture: MCP module with one @mcp.tool and three internal helpers.

  write_record   — @mcp.tool → exposure mcp_tool
  _helper_a      — internal function with side effect → mcp_internal
  _helper_b      — internal function with side effect → mcp_internal
  _helper_c      — internal function with side effect → mcp_internal
"""
from __future__ import annotations

import subprocess

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("test")


@mcp.tool()
async def write_record(name: str) -> str:
    subprocess.run(["write", name], check=True)
    return "ok"


def _helper_a(x: str) -> None:
    subprocess.run(["a", x], check=True)


def _helper_b(x: str) -> None:
    subprocess.run(["b", x], check=True)


def _helper_c(x: str) -> None:
    subprocess.run(["c", x], check=True)
