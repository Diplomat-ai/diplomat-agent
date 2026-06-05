"""Tests for SPEC-FIX-SCANNER-CORRECTNESS-v1.

FIX 1 — SyntaxError / BOM handling
FIX 2 — Reader-prefix false-positive elimination
FIX 3 — Cross-module MCP gate
FIX 4 — Dispatcher-file tracking in last_scan_stats
"""
from __future__ import annotations

import io
import sys
import textwrap
from pathlib import Path

import pytest

from diplomat_agent.scanner.ast_scanner import scan_file, scan_directory, last_scan_stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


def _make_py(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# FIX 1 — SyntaxError: warn + track + return []
# ---------------------------------------------------------------------------

BAD_ESCAPE_FIXTURE = FIXTURES / "broken" / "bad_escape.py"


def test_fix1_syntax_error_returns_empty(tmp_path):
    """scan_file on a file with invalid \\U escape must return []."""
    # Create a file with a guaranteed SyntaxError (invalid \\U escape)
    bad = tmp_path / "bad.py"
    bad.write_bytes(b"def f():\n    x = 'C:\\Users\\test'\n")
    result = scan_file(bad)
    assert result == []


def test_fix1_syntax_error_warns_stderr(tmp_path, capsys):
    """scan_file must emit a warning to stderr when SyntaxError occurs."""
    bad = tmp_path / "bad.py"
    bad.write_bytes(b"def f():\n    x = 'C:\\Users\\test'\n")
    scan_file(bad)
    captured = capsys.readouterr()
    assert "SyntaxError" in captured.err or "could not parse" in captured.err


def test_fix1_syntax_error_populates_parse_errors(tmp_path):
    """scan_file must append to _parse_errors when SyntaxError occurs."""
    bad = tmp_path / "bad.py"
    bad.write_bytes(b"def f():\n    x = 'C:\\Users\\test'\n")
    errors: list[str] = []
    result = scan_file(bad, _parse_errors=errors)
    assert result == []
    assert len(errors) == 1
    assert "bad.py" in errors[0]


def test_fix1_bom_file_parses_without_error(tmp_path):
    """A UTF-8 BOM file must be parsed successfully (no SyntaxError)."""
    content = "def greet(name: str) -> str:\n    return f'Hello {name}'\n"
    bom_file = tmp_path / "bom_file.py"
    # Write with BOM
    bom_file.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
    errors: list[str] = []
    result = scan_file(bom_file, _parse_errors=errors)
    # No parse error expected
    assert errors == []


def test_fix1_scan_directory_tracks_unparsed(tmp_path):
    """scan_directory must surface files_unparsed in last_scan_stats."""
    # Good file
    good = tmp_path / "good.py"
    good.write_text("def nothing(): pass\n", encoding="utf-8")
    # Bad file
    bad = tmp_path / "bad.py"
    bad.write_bytes(b"def f():\n    x = 'C:\\Users\\test'\n")

    scan_directory(tmp_path)
    from diplomat_agent.scanner import ast_scanner
    stats = dict(ast_scanner.last_scan_stats)
    assert "files_unparsed" in stats
    assert len(stats["files_unparsed"]) == 1
    assert "bad.py" in stats["files_unparsed"][0]


# ---------------------------------------------------------------------------
# FIX 2 — Reader-prefix false-positive elimination
# ---------------------------------------------------------------------------

def test_fix2_get_post_not_detected_as_http_write(tmp_path):
    """client.get_post(uri) must NOT be flagged as an http_write side effect."""
    src = _make_py(tmp_path, "reader_fp.py", """\
        import httpx

        def fetch_post(uri: str):
            client = httpx.Client()
            return client.get_post(uri)
    """)
    tools = scan_file(src)
    # No tool should be returned (no write side-effect)
    assert tools == []


def test_fix2_get_prefixed_methods_are_read_only(tmp_path):
    """Methods starting with get_, list_, fetch_ etc. must not be side-effects."""
    src = _make_py(tmp_path, "readers.py", """\
        def run(client):
            client.get_items()
            client.list_users()
            client.fetch_data()
            client.search_records()
            client.query_db()
            client.find_one()
            client.describe_index()
            client.show_tables()
            client.read_config()
    """)
    tools = scan_file(src)
    assert tools == []


def test_fix2_write_methods_still_detected(tmp_path):
    """Methods like post(), put(), delete() must still be flagged."""
    src = _make_py(tmp_path, "writes.py", """\
        import requests

        def publish(url: str, data: dict):
            requests.post(url, json=data)
    """)
    tools = scan_file(src)
    assert len(tools) == 1
    assert any(se.category == "http_write" for se in tools[0].side_effects)


def test_fix2_delete_post_still_detected(tmp_path):
    """delete_post() does NOT start with a reader prefix — must still fire."""
    src = _make_py(tmp_path, "delete_post.py", """\
        import requests

        def remove_post(uri: str):
            requests.delete(uri)
    """)
    tools = scan_file(src)
    assert len(tools) == 1


# ---------------------------------------------------------------------------
# FIX 3 — Cross-module MCP gate
# ---------------------------------------------------------------------------

def test_fix3_cross_module_mcp_gate(tmp_path):
    """A tool that imports `mcp` from a local module should be classified as mcp_tool."""
    # Create a minimal package
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    # server.py — provides the MCP instance (imports from the real SDK)
    (pkg / "server.py").write_text(
        "from mcp.server.fastmcp import FastMCP\nmcp = FastMCP('test')\n",
        encoding="utf-8",
    )
    # tools.py — imports `mcp` from server.py (cross-module)
    (pkg / "tools.py").write_text(
        "import os\nfrom .server import mcp\n\n"
        "@mcp.tool()\ndef wipe(path: str) -> str:\n    os.remove(path)\n    return path\n",
        encoding="utf-8",
    )
    tools = scan_file(pkg / "tools.py")
    assert len(tools) == 1, f"Expected 1 tool, got {len(tools)}"
    assert tools[0].exposure == "mcp_tool", f"Expected mcp_tool, got {tools[0].exposure}"


def test_fix3_non_mcp_import_not_promoted(tmp_path):
    """Importing a variable named `mcp` without @mcp.tool() must NOT promote the file."""
    src = _make_py(tmp_path, "no_mcp.py", """\
        from some.random import mcp

        def do_work():
            result = mcp.process()
            return result
    """)
    tools = scan_file(src)
    # No mcp_tool exposure since no @mcp.tool() decorator
    assert all(t.exposure != "mcp_tool" for t in tools)


# ---------------------------------------------------------------------------
# FIX 4 — Dispatcher-file tracking
# ---------------------------------------------------------------------------

def test_fix4_dispatcher_file_tracked(tmp_path):
    """A file with @server.call_tool must appear in _dispatcher_files."""
    src = _make_py(tmp_path, "dispatcher.py", """\
        from mcp.server import Server

        server = Server("test")

        @server.call_tool()
        async def handle_tool(name: str, arguments: dict):
            import os
            os.system(arguments["cmd"])
    """)
    dispatchers: list[str] = []
    scan_file(src, _dispatcher_files=dispatchers)
    assert len(dispatchers) == 1
    assert "dispatcher.py" in dispatchers[0]


def test_fix4_scan_directory_tracks_dispatcher_files(tmp_path):
    """scan_directory must populate dispatcher_files in last_scan_stats."""
    (tmp_path / "normal.py").write_text("def safe(): pass\n", encoding="utf-8")
    (tmp_path / "dispatch.py").write_text(
        "from mcp.server import Server\n"
        "server = Server('t')\n"
        "@server.call_tool()\n"
        "async def handle(name, arguments):\n"
        "    import os; os.system(arguments['cmd'])\n",
        encoding="utf-8",
    )
    scan_directory(tmp_path)
    from diplomat_agent.scanner import ast_scanner
    stats = dict(ast_scanner.last_scan_stats)
    assert "dispatcher_files" in stats
    assert len(stats["dispatcher_files"]) == 1
    assert "dispatch.py" in stats["dispatcher_files"][0]
