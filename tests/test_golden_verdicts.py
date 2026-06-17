"""Golden verdict table — intent-anchored regression guard for v0.5.2.

Each expected verdict is written from the SPEC INTENT, not copied from output.
Any future drift in scanner behavior will fail this test loudly.

Run with: python -m pytest tests/test_golden_verdicts.py -v
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_agent.analyzer.guards import apply_verdicts
from diplomat_agent.scanner.ast_scanner import scan_file
from diplomat_agent.scanner.interprocedural import PackageIndex

MCP_FIXTURES = Path(__file__).parent / "fixtures" / "mcp"

_MCP_HDR = """\
from __future__ import annotations
from fastmcp import FastMCP
mcp = FastMCP("t")
"""


def _scan_snippet(code: str, use_pkg: bool = False) -> dict:
    """Write code to a temp file, scan it, return {name: Tool}."""
    tmp = tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, encoding="utf-8"
    )
    tmp.write(code)
    tmp.close()
    p = Path(tmp.name)
    pkg = PackageIndex(p.parent) if use_pkg else None
    try:
        tools = scan_file(p, package_index=pkg)
        apply_verdicts(tools)
        return {t.name: t for t in tools}
    finally:
        os.unlink(tmp.name)


# ---------------------------------------------------------------------------
# 1. Benign builtin read (no MCP context)
#    str.upper() + dict.get() → no external effect → no finding.
# ---------------------------------------------------------------------------
def test_golden_1_benign_builtin_read():
    """def f(s:str, d:dict): return s.upper()+str(d.get('k')) → no finding."""
    tools = _scan_snippet('def f(s:str,d:dict): return s.upper()+str(d.get("k"))')
    assert not tools, (
        f"Expected no findings for pure builtin read; got {list(tools)}"
    )


# ---------------------------------------------------------------------------
# 2. Benign builtin mutate (no MCP context)
#    list.append() on a typed list param → in-memory only → no finding.
# ---------------------------------------------------------------------------
def test_golden_2_benign_builtin_mutate():
    """def f(x:list): x.append(1) → no finding (in-memory mutation)."""
    tools = _scan_snippet("def f(x:list): x.append(1)")
    assert not tools, (
        f"Expected no findings for in-memory list.append; got {list(tools)}"
    )


# ---------------------------------------------------------------------------
# 3. Untyped mutator — @mcp.tool, untyped receiver, .add()
#    cache is untyped; cache.add(k, v) has unknown semantics → OPAQUE.
#    Must NOT be silently dropped.
# ---------------------------------------------------------------------------
def test_golden_3_untyped_mutator_is_opaque():
    """@mcp.tool def f(cache,k,v): cache.add(k,v) → OPAQUE (untyped cache)."""
    tools = _scan_snippet(_MCP_HDR + "@mcp.tool()\ndef f(cache,k,v): cache.add(k,v)")
    assert "f" in tools, (
        f"write_cache (f) must be detected; got {list(tools)}"
    )
    assert tools["f"].verdict == "OPAQUE", (
        f"Untyped cache.add must be OPAQUE; got {tools['f'].verdict!r}, "
        f"opaque_reason={tools['f'].opaque_reason!r}"
    )


# ---------------------------------------------------------------------------
# 4. Untyped custom method — @mcp.tool, untyped receiver, unknown method
#    h.dispatch(p): receiver h is untyped, dispatch is not a recognized verb.
#    → OPAQUE.
# ---------------------------------------------------------------------------
def test_golden_4_untyped_dispatch_is_opaque():
    """@mcp.tool def f(h,p): return h.dispatch(p) → OPAQUE (untyped h)."""
    tools = _scan_snippet(_MCP_HDR + "@mcp.tool()\ndef f(h,p): return h.dispatch(p)")
    assert "f" in tools, f"f must be detected; got {list(tools)}"
    assert tools["f"].verdict == "OPAQUE", (
        f"Untyped h.dispatch must be OPAQUE; got {tools['f'].verdict!r}"
    )


# ---------------------------------------------------------------------------
# 5. Recognized write verb on a receiver — @mcp.tool, self.driver.execute_query
#    execute_query is in SIDE_EFFECT_PATTERNS (attr_exact, database_write).
#    The pattern detector catches it BEFORE the OPAQUE floor, so verdict is
#    UNGUARDED (more informative than OPAQUE — we know it's a database write).
# ---------------------------------------------------------------------------
def test_golden_5_recognized_verb_is_unguarded():
    """@mcp.tool def f(self, q): self.driver.execute_query(q)
    → UNGUARDED (execute_query is a recognized database_write pattern).
    Note: UNGUARDED is more informative than OPAQUE here."""
    tools = _scan_snippet(
        _MCP_HDR + "@mcp.tool()\ndef f(self, q): return self.driver.execute_query(q)"
    )
    assert "f" in tools, f"f must be detected; got {list(tools)}"
    assert tools["f"].verdict == "UNGUARDED", (
        f"execute_query is a recognized verb → verdict must be UNGUARDED; "
        f"got {tools['f'].verdict!r}"
    )
    cats = {se.category for se in tools["f"].side_effects}
    assert "database_write" in cats, (
        f"execute_query must produce database_write side effect; got {cats}"
    )


# ---------------------------------------------------------------------------
# 6. self.method → subprocess (étage-2 self resolution)
#    Class method @mcp.tool calls self._do_write which calls os.remove.
#    Étage-2 resolution must surface the file_delete → UNGUARDED.
# ---------------------------------------------------------------------------
def test_golden_6_self_method_subprocess_unguarded():
    """@mcp.tool self.method() → resolved class method → os.remove → UNGUARDED."""
    fixture = MCP_FIXTURES / "etage2_self_method.py"
    pkg = PackageIndex(fixture.parent)
    tools = scan_file(fixture, package_index=pkg)
    apply_verdicts(tools)
    by_name = {t.name: t for t in tools}
    assert "run" in by_name, f"run not found; got {list(by_name)}"
    assert by_name["run"].verdict == "UNGUARDED", (
        f"self._do_write → os.remove must resolve to UNGUARDED; "
        f"got {by_name['run'].verdict!r}"
    )


# ---------------------------------------------------------------------------
# 7. Typed local binding → write (étage-2 local binding resolution)
#    w = Writer(); w.run(path) resolves Writer.run → os.remove → UNGUARDED.
# ---------------------------------------------------------------------------
def test_golden_7_typed_local_binding_unguarded():
    """w = Writer(); w.run(path) → Writer.run → os.remove → UNGUARDED."""
    fixture = MCP_FIXTURES / "etage2_local_binding.py"
    pkg = PackageIndex(fixture.parent)
    tools = scan_file(fixture, package_index=pkg)
    apply_verdicts(tools)
    by_name = {t.name: t for t in tools}
    assert "handler" in by_name, f"handler not found; got {list(by_name)}"
    assert by_name["handler"].verdict == "UNGUARDED", (
        f"w=Writer(); w.run(path) must resolve to UNGUARDED; "
        f"got {by_name['handler'].verdict!r}"
    )


# ---------------------------------------------------------------------------
# 8. Reassigned receiver — @mcp.tool
#    r=Reader(); r=get_writer(); r.flush() → r's type is uncertain → OPAQUE.
# ---------------------------------------------------------------------------
def test_golden_8_reassigned_receiver_is_opaque():
    """r=Reader(); r=get_writer(); r.flush() → OPAQUE (type dropped after reassignment)."""
    fixture = MCP_FIXTURES / "reassigned_var.py"
    pkg = PackageIndex(fixture.parent)
    tools = scan_file(fixture, package_index=pkg)
    apply_verdicts(tools)
    by_name = {t.name: t for t in tools}
    assert "handler" in by_name, f"handler not found; got {list(by_name)}"
    assert by_name["handler"].verdict == "OPAQUE", (
        f"Reassigned receiver must be OPAQUE; got {by_name['handler'].verdict!r}"
    )


# ---------------------------------------------------------------------------
# 9. Recognized write patterns — caught by SIDE_EFFECT_PATTERNS (no MCP)
#    collection.insert(doc) → database_write → UNGUARDED
#    db.remove(doc)          → database_delete → UNGUARDED
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("code,expected_cat", [
    ("def f(collection, doc): collection.insert(doc)", "database_write"),
    ("def f(db, doc): db.remove(doc)", "database_delete"),
])
def test_golden_9_recognized_write_patterns(code, expected_cat):
    """Recognized write/delete verbs are caught by SIDE_EFFECT_PATTERNS → UNGUARDED."""
    tools = _scan_snippet(code)
    assert tools, f"Expected UNGUARDED finding for: {code!r}; got no findings"
    tool = list(tools.values())[0]
    assert tool.verdict == "UNGUARDED", (
        f"Expected UNGUARDED for {expected_cat}; got {tool.verdict!r}"
    )
    cats = {se.category for se in tool.side_effects}
    assert expected_cat in cats, (
        f"Expected {expected_cat} in side effects; got {cats}"
    )


# ---------------------------------------------------------------------------
# 10. MCP client passthrough — session.call_tool() is an opaque remote proxy
#     → OPAQUE with opaque_reason mentioning mcp_client or remote.
# ---------------------------------------------------------------------------
def test_golden_10_mcp_client_passthrough_is_opaque():
    """session.call_tool(name, args) with MCP client import → OPAQUE."""
    fixture = Path(__file__).parent / "fixtures" / "external_mcp_client.py"
    tools = scan_file(fixture)
    apply_verdicts(tools)
    by_name = {t.name: t for t in tools}
    assert by_name, f"Expected OPAQUE mcp_client tools; got none"
    # All tools in external_mcp_client must be OPAQUE
    for name, tool in by_name.items():
        assert tool.verdict == "OPAQUE", (
            f"MCP client tool {name!r} must be OPAQUE; got {tool.verdict!r}"
        )
        assert tool.opaque_reason, (
            f"MCP client tool {name!r} must have non-empty opaque_reason"
        )
