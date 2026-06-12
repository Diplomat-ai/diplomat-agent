"""PHASE 4 locking fixture: sleep is never an external side effect.

`asyncio.sleep`, `time.sleep`, and `trio.sleep` are wait primitives — they
never reach an external service. They must NOT trigger OPAQUE.
"""
from __future__ import annotations

import asyncio
import time

from fastmcp import FastMCP

mcp = FastMCP("t")


@mcp.tool()
async def waits(seconds):
    await asyncio.sleep(seconds)  # must be CLEAN (no external effect)
    time.sleep(0.1)               # must be CLEAN
    return "done"
