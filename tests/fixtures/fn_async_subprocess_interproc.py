from __future__ import annotations
import asyncio


async def _run(cmd):
    return await asyncio.create_subprocess_exec(*cmd)


async def tool_entry(cmd):
    """plain-Name call must propagate the side effect up via interproc."""
    return await _run(cmd)
