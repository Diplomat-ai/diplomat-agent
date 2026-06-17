"""GATE 2 fixtures — executor callable indirection (asyncio.to_thread / run_in_executor).

Expected verdicts after v0.5.3 GATE 2 fix:
  run_it          → OPAQUE  (to_thread(client.containers.run, ...) — non-benign attr callable)
  nested_closure  → OPAQUE  (reproduces handle_create_container: inner closure calls to_thread)
  benign_thread   → clean   (to_thread(json.dumps, data) — benign callable)
  benign_len      → clean   (to_thread(len, x) — benign builtin)
  sleep_tool      → clean   (asyncio.sleep — benign attr, was regression-tested in v0.5.2)
  run_in_exec     → OPAQUE  (loop.run_in_executor(None, client.do_write, arg))
"""
from __future__ import annotations

import asyncio
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("executor-test")


# -----------------------------------------------------------------------
# Positive: should be OPAQUE
# -----------------------------------------------------------------------

@mcp.tool()
async def run_it(client):
    """asyncio.to_thread(client.containers.run, 'img') — non-benign callable attr."""
    container = await asyncio.to_thread(client.containers.run, "img")
    return {"id": container.id}


@mcp.tool()
async def nested_closure(docker_client, image: str):
    """Reproduces docker-mcp create-container: callable inside a nested async def."""
    async def pull_and_run():
        if not docker_client.image.exists(image):
            await asyncio.to_thread(docker_client.image.pull, image)
        container = await asyncio.to_thread(
            docker_client.container.run,
            image,
            detach=True,
        )
        return container

    result = await asyncio.wait_for(pull_and_run(), timeout=60)
    return {"container": result.name}


@mcp.tool()
async def run_in_exec(loop, client, arg):
    """loop.run_in_executor(None, client.do_write, arg) — non-benign callable attr."""
    result = await loop.run_in_executor(None, client.do_write, arg)
    return {"result": result}


# -----------------------------------------------------------------------
# Negative: must NOT be OPAQUE (benign callables)
# -----------------------------------------------------------------------

@mcp.tool()
async def benign_thread(data: dict):
    """to_thread(json.dumps, data) — json.dumps is benign (BENIGN_ATTR_METHODS: dumps)."""
    import json
    serialised = await asyncio.to_thread(json.dumps, data)
    return {"out": serialised}


@mcp.tool()
async def benign_len(items: list):
    """to_thread(len, items) — len is benign (BENIGN_BUILTIN_NAMES)."""
    n = await asyncio.to_thread(len, items)
    return {"count": n}


@mcp.tool()
async def sleep_tool(seconds: float):
    """asyncio.sleep regression: must remain clean (sleep is in BENIGN_ATTR_METHODS)."""
    await asyncio.sleep(seconds)
    return {"slept": seconds}
