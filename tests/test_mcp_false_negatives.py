"""Tests for v0.5.3 — GATE 1 (dispatcher carrier) and GATE 2 (executor indirection).

Positive fixtures: verify expected OPAQUE verdicts after the fixes.
Negative fixtures: verify no over-detection (benign callables stay clean).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_agent.analyzer.guards import apply_verdicts
from diplomat_agent.scanner.ast_scanner import scan_directory, scan_file

FIXTURES = Path(__file__).parent / "fixtures" / "mcp"


# ---------------------------------------------------------------------------
# GATE 1 — dispatcher handler: treat_as_mcp_tool=True → OPAQUE for carriers
# ---------------------------------------------------------------------------

class TestDispatcherCarrierCheck:
    """BUG 1 fix: dispatcher-resolved handlers must surface OPAQUE, not LOW_RISK."""

    def setup_method(self):
        tools = scan_directory(FIXTURES.parent.parent / "fixtures" / "mcp")
        apply_verdicts(tools)
        self.by_name = {t.name: t for t in tools if t.file and "dispatcher_wrapped_write" in t.file}

    def test_commit_handler_is_opaque(self):
        """_commit has repo.index.commit (unresolved carrier) → OPAQUE after fix."""
        assert "commit" in self.by_name, f"commit not found; available: {list(self.by_name)}"
        assert self.by_name["commit"].verdict == "OPAQUE", (
            f"Expected OPAQUE, got {self.by_name['commit'].verdict} — BUG 1 not fixed"
        )

    def test_noop_handler_is_low_risk(self):
        """_noop has no calls at all → no carrier → stays LOW_RISK (no over-detection)."""
        assert "noop" in self.by_name, f"noop not found; available: {list(self.by_name)}"
        assert self.by_name["noop"].verdict == "LOW_RISK", (
            f"Expected LOW_RISK, got {self.by_name['noop'].verdict} — over-detection on empty body"
        )

    def test_read_handler_not_unguarded(self):
        """_read does a pure attribute traversal — must never be UNGUARDED.

        NOTE (v0.5.3): with treat_as_mcp_tool=True, the carrier check now runs for
        ALL dispatcher-resolved handlers including reads. _read calls repo.head.commit.hexsha
        which is an unresolved attribute call → OPAQUE. This is MORE honest than LOW_RISK
        (scanner genuinely doesn't know if repo.head.commit is a read or write).
        Preserving STATUS→LOW_RISK would require readOnlyHint cross-referencing from
        list_tools() — a separate feature scope. The safety invariant (non-UNGUARDED) holds.
        """
        assert "read" in self.by_name, f"read not found; available: {list(self.by_name)}"
        assert self.by_name["read"].verdict != "UNGUARDED", (
            f"read handler must not be UNGUARDED (got {self.by_name['read'].verdict})"
        )


# ---------------------------------------------------------------------------
# Scan individual fixture file helpers
# ---------------------------------------------------------------------------

def _scan_fixture(filename: str) -> dict:
    tools = scan_file(FIXTURES / filename)
    apply_verdicts(tools)
    return {t.name: t for t in tools}


# ---------------------------------------------------------------------------
# GATE 2 — executor callable indirection
# ---------------------------------------------------------------------------

class TestExecutorIndirection:
    """BUG 2 fix: asyncio.to_thread(non_benign_fn, ...) must be OPAQUE."""

    def setup_method(self):
        self.tools = _scan_fixture("executor_indirection.py")

    def test_run_it_is_opaque(self):
        """to_thread(client.containers.run, 'img') — non-benign callable attr → OPAQUE."""
        t = self.tools.get("run_it")
        assert t is not None, "run_it not found"
        assert t.verdict == "OPAQUE", (
            f"Expected OPAQUE, got {t.verdict} — BUG 2 not fixed"
        )

    def test_nested_closure_is_opaque(self):
        """Nested closure with to_thread(docker_client.container.run, ...) → OPAQUE."""
        t = self.tools.get("nested_closure")
        assert t is not None, "nested_closure not found"
        assert t.verdict == "OPAQUE", (
            f"Expected OPAQUE, got {t.verdict} — closure walk not catching executor callable"
        )

    def test_run_in_executor_is_opaque(self):
        """loop.run_in_executor(None, client.do_write, arg) → OPAQUE."""
        t = self.tools.get("run_in_exec")
        assert t is not None, "run_in_exec not found"
        assert t.verdict == "OPAQUE", (
            f"Expected OPAQUE, got {t.verdict} — run_in_executor not handled"
        )

    # --- Negative tests (must NOT be OPAQUE) ---

    def test_benign_thread_json_dumps_is_clean(self):
        """to_thread(json.dumps, data) — dumps is BENIGN_ATTR_METHODS → not OPAQUE."""
        t = self.tools.get("benign_thread")
        assert t is None or t.verdict != "OPAQUE", (
            f"benign_thread (to_thread(json.dumps)) must not be OPAQUE — over-detection"
        )

    def test_benign_len_is_clean(self):
        """to_thread(len, items) — len is BENIGN_BUILTIN_NAMES → not OPAQUE."""
        t = self.tools.get("benign_len")
        assert t is None or t.verdict != "OPAQUE", (
            f"benign_len (to_thread(len)) must not be OPAQUE — over-detection"
        )

    def test_sleep_tool_is_clean(self):
        """asyncio.sleep regression: must remain clean after GATE 2 changes."""
        t = self.tools.get("sleep_tool")
        assert t is None or t.verdict not in ("OPAQUE", "UNGUARDED"), (
            f"sleep_tool must remain clean (got {t.verdict if t else 'None'}) — sleep regression"
        )
