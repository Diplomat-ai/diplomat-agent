"""PHASE 1 locking fixture: ambiguous mutator names on typed vs untyped receivers.

write_cache: cache is UNTYPED — cache.add(k, v) is an unknown external call.
             Expected verdict: OPAQUE (unknown effect surface, must not be dropped).

append_list: items is typed as builtin `list` — items.append(x) is in-memory only.
             Expected verdict: no finding / not OPAQUE (type-aware skip).
"""
from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("t")


@mcp.tool()
def write_cache(cache, k, v):  # cache: untyped custom receiver
    cache.add(k, v)            # must be OPAQUE (unknown effect surface)


@mcp.tool()
def append_list(items: list, x):  # items: typed builtin
    items.append(x)               # must be CLEAN (in-memory, type-aware skip)
