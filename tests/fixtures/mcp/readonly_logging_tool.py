"""GATE 1 negative fixture: read-only tool with benign logging — must NOT be OPAQUE."""
from __future__ import annotations

import logging

from fastmcp import FastMCP

mcp = FastMCP("readonly-logging")
logger = logging.getLogger(__name__)

STATUS_OK = "ok"


@mcp.tool()
def status() -> str:
    logger.info("status checked")
    return STATUS_OK
