"""GATE 5 fixture: @server.call_tool dispatcher using if/elif, same-file class method handler.

  handle_tools  — @server.call_tool dispatcher (must NOT appear as a Tool)
  H.create      — class method handler for "create"; calls subprocess.run (destructive)
"""
from __future__ import annotations

import subprocess

from mcp.server import Server

server = Server("test")


class H:
    @staticmethod
    async def create(args: dict) -> list:
        subprocess.run(["docker", "run", args["image"]], check=True)
        return []


@server.call_tool()
async def handle_tools(name: str, arguments: dict) -> list:
    if name == "create":
        return await H.create(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")
