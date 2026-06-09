from __future__ import annotations
import asyncio


async def execute_command(command: str):
    return await asyncio.create_subprocess_exec("kubectl", *command.split())  # destructive
