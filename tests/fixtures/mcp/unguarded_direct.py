"""Golden table GATE 3 fixture: direct @mcp.tool with subprocess.run → UNGUARDED.

subprocess.run is in SIDE_EFFECT_PATTERNS (destructive), no guards present → UNGUARDED.
"""
from __future__ import annotations

import subprocess
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("unguarded-test")


@mcp.tool()
def run_command(cmd: str) -> str:
    """Run a shell command — subprocess.run is detected UNGUARDED (no guard present)."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout
