"""GATE 5 cross-file fixture: dispatcher in server.py calls Handlers from handlers.py."""
from __future__ import annotations

from mcp.server import Server

from .handlers import Handlers

server = Server("test")


@server.call_tool()
async def handle_tools(name: str, arguments: dict) -> list:
    if name == "create":
        return await Handlers.create(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")
