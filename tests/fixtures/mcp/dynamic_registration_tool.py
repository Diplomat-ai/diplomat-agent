"""GATE 4 fixture: dynamic registration via mcp.tool(name=...)(fn).

Mirrors awslabs/lambda-tool — the function is registered programmatically with
a curried decorator factory. Expected: lambda_function surfaces as exposure
mcp_tool (not internal).
"""
from __future__ import annotations

import os

from fastmcp import FastMCP

mcp = FastMCP("dynamic-registration")


def lambda_function(payload: dict) -> dict:
    os.remove(payload["target"])
    return {"ok": True}


# Curried registration — outer Call applies mcp.tool(...) factory to fn.
mcp.tool(name="invoke_lambda", description="Invoke target")(lambda_function)
