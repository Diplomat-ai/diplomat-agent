"""GATE 3a — Golden verdict table (10 cases, verdicts from intent, not from output).

Each case has an expected verdict written from the INTENTION of the test, not copied from
scan output. All 10 must pass.

Column mapping:
  case_id   | fixture inline code   | expected_verdict | rationale
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_agent.analyzer.guards import apply_verdicts
from diplomat_agent.scanner.ast_scanner import scan_directory, scan_file

FIXTURES = Path(__file__).parent / "fixtures" / "mcp"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scan_code_mcp(code: str):
    """Write code to a temp .py file and scan it with MCP detection active."""
    tmpf = tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, dir=None)
    tmpf.write(code)
    tmpf.close()
    try:
        tools = scan_file(Path(tmpf.name))
        apply_verdicts(tools)
        return {t.name: t for t in tools}
    finally:
        os.unlink(tmpf.name)


def _scan_fixture_file(filename: str):
    tools = scan_file(FIXTURES / filename)
    apply_verdicts(tools)
    return {t.name: t for t in tools}


def _scan_fixture_dir(fixture_name: str):
    """Scan a named fixture directory under tests/fixtures/."""
    d = Path(__file__).parent / "fixtures" / fixture_name
    tools = scan_directory(d)
    apply_verdicts(tools)
    return {t.name: t for t in tools}


# ---------------------------------------------------------------------------
# 10-case golden table
# ---------------------------------------------------------------------------

GOLDEN_CASES = [
    # --- GATE 1: dispatcher handler with unresolved write ---
    pytest.param(
        "dispatcher_wrapped_write.py", "commit",
        "OPAQUE",
        "dispatcher → handler with unresolved write (repo.index.commit) must be OPAQUE",
        id="G1-dispatcher-write",
    ),
    # --- GATE 1: dispatcher handler with empty body ---
    pytest.param(
        "dispatcher_wrapped_write.py", "noop",
        "LOW_RISK",
        "dispatcher → handler with pure literal return (no calls) must be LOW_RISK",
        id="G1-dispatcher-noop",
    ),
    # --- GATE 1: dispatcher handler read-only — must NOT be UNGUARDED ---
    pytest.param(
        "dispatcher_wrapped_write.py", "read",
        "!UNGUARDED",
        "dispatcher → read-only handler must never be UNGUARDED",
        id="G1-dispatcher-read-not-unguarded",
    ),
    # --- Direct @mcp.tool with subprocess.run → UNGUARDED ---
    pytest.param(
        "unguarded_direct.py", "run_command",
        "UNGUARDED",
        "@mcp.tool direct with subprocess.run (known write pattern) must be UNGUARDED",
        id="G2-direct-subprocess",
    ),
    # --- Direct @mcp.tool with unresolved obj.method() → OPAQUE ---
    pytest.param(
        "executor_indirection.py", "run_it",
        "OPAQUE",
        "@mcp.tool with to_thread(client.containers.run) must be OPAQUE",
        id="G2-executor-attr-carrier",
    ),
    # --- to_thread with non-benign callable attr → OPAQUE ---
    pytest.param(
        "executor_indirection.py", "nested_closure",
        "OPAQUE",
        "nested closure with to_thread(client.container.run) must be OPAQUE",
        id="G2-executor-nested-closure",
    ),
    # --- to_thread with benign callable (json.dumps) → clean ---
    pytest.param(
        "executor_indirection.py", "benign_thread",
        "clean",
        "to_thread(json.dumps, data) must NOT be OPAQUE (benign callable)",
        id="G2-executor-benign-callable",
    ),
    # --- asyncio.sleep → clean (v0.5.2 regression) ---
    pytest.param(
        "executor_indirection.py", "sleep_tool",
        "clean",
        "asyncio.sleep must remain clean (BENIGN_ATTR_METHODS: sleep)",
        id="G2-sleep-benign",
    ),
    # --- mcp_client session.call_tool() → OPAQUE ---
    pytest.param(
        "mcp_client_call.py", "proxy_call",
        "OPAQUE",
        "mcp_client session.call_tool() must be OPAQUE",
        id="G3-mcp-client-proxy",
    ),
    # --- builtin typed s.upper() / d.get() → clean ---
    pytest.param(
        "benign_typed_call.py", "fmt",
        "clean",
        "builtin-typed s.upper() / d.get() must remain clean (no OPAQUE on stdlib)",
        id="G3-builtin-typed",
    ),
    # --- GATE 1 (Show HN): list literal + to_thread → OPAQUE (via executor, NOT via append) ---
    pytest.param(
        "literal_type_bindings.py", "list_with_executor",
        "OPAQUE",
        "list literal + to_thread must be OPAQUE; append on list must not be the carrier",
        id="G4-literal-list-executor",
    ),
    # --- GATE 1 (Show HN): dict literal + .get() only → clean ---
    pytest.param(
        "literal_type_bindings.py", "dict_read_only",
        "clean",
        "dict literal with only .get() calls must stay clean (no external effects)",
        id="G4-literal-dict-clean",
    ),
    # --- GATE 1 (Show HN): list literal + .append() only → clean ---
    pytest.param(
        "literal_type_bindings.py", "list_append_only",
        "clean",
        "list literal with only .append() calls must stay clean (no external effects)",
        id="G4-literal-list-append-clean",
    ),
]


@pytest.mark.parametrize("fixture_file,tool_name,expected,rationale", GOLDEN_CASES)
def test_golden_verdict(fixture_file, tool_name, expected, rationale):
    """Run each golden case and assert the expected verdict."""
    tools = _scan_fixture_file(fixture_file)
    tool = tools.get(tool_name)

    if expected == "clean":
        assert tool is None or tool.verdict not in ("OPAQUE", "UNGUARDED"), (
            f"[{tool_name}] expected clean (no OPAQUE/UNGUARDED). Got {tool.verdict if tool else 'None'}. "
            f"Rationale: {rationale}"
        )
    elif expected == "!UNGUARDED":
        if tool is not None:
            assert tool.verdict != "UNGUARDED", (
                f"[{tool_name}] must not be UNGUARDED. Got {tool.verdict}. Rationale: {rationale}"
            )
    else:
        assert tool is not None, (
            f"[{tool_name}] not found in {fixture_file}. Available: {list(tools)}. "
            f"Rationale: {rationale}"
        )
        assert tool.verdict == expected, (
            f"[{tool_name}] expected {expected}, got {tool.verdict}. Rationale: {rationale}"
        )
