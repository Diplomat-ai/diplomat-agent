"""GATE 5 fixture: @server.call_tool dispatcher using match/case (Python 3.10+).

  handle_tools  — @server.call_tool dispatcher (must NOT appear as a Tool)
  do_commit     — plain-Name handler for "commit"; calls subprocess.run (destructive)
  do_read       — plain-Name handler for "list"; no write effects → LOW_RISK dispatched tool
"""
from __future__ import annotations

import subprocess

from mcp.server import Server

server = Server("test")


def do_commit(repo: str, msg: str) -> None:
    subprocess.run(["git", "commit", "-m", msg], check=True)


def do_read(repo: str) -> list:
    return []


@server.call_tool()
async def handle_tools(name: str, arguments: dict) -> list:
    match name:
        case "commit":
            do_commit(arguments["repo"], arguments["msg"])
            return []
        case "list":
            return do_read(arguments.get("repo", ""))
