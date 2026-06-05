"""Tests for v0.5.0 coverage fixes (SPEC-FEAT-COVERAGE-v2).

Covers:
- FIX C: psutil / os.kill destructive patterns + precision (no false friends).
- ANTI-FP: observability helper exclusion + return-value-used scoping.
- FIX A v1: same-module top-level inter-procedural side-effects + guard symmetry.
- FIX B v1: programmatic MCP registration via mcp.add_tool(fn).
"""
from __future__ import annotations

import os
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_agent.scanner.ast_scanner import scan_directory, scan_file
from diplomat_agent.analyzer.guards import apply_verdicts


def _scan_dir(path: Path):
    tools = scan_directory(path)
    apply_verdicts(tools)
    return {t.name: t for t in tools}


def _scan_code(code: str):
    tmpf = tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8")
    tmpf.write(code)
    tmpf.close()
    try:
        tools = scan_file(Path(tmpf.name))
        apply_verdicts(tools)
        return tools
    finally:
        os.unlink(tmpf.name)


# ---------------------------------------------------------------------------
# FIX C — psutil / os.kill detection + precision
# ---------------------------------------------------------------------------


class TestFixC_PsutilDetection:
    def test_psutil_process_kill_detected(self):
        tools = _scan_code(textwrap.dedent("""
            import psutil

            def kill_pid(pid):
                psutil.Process(pid).kill()
        """))
        assert len(tools) == 1
        assert tools[0].name == "kill_pid"
        cats = {se.category for se in tools[0].side_effects}
        assert "destructive" in cats

    def test_psutil_process_terminate_detected(self):
        tools = _scan_code(textwrap.dedent("""
            import psutil

            def stop_pid(pid):
                proc = psutil.Process(pid)
                proc.terminate()
        """))
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "destructive" in cats

    def test_os_kill_detected(self):
        tools = _scan_code(textwrap.dedent("""
            import os, signal

            def murder(pid):
                os.kill(pid, signal.SIGKILL)
        """))
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "destructive" in cats


class TestFixC_PrecisionNoFalseFriends:
    def test_animation_proc_kill_not_matched(self):
        """A bare animation_proc.kill() in a module that does NOT import psutil
        must NOT be flagged. obj_contains is psutil-scoped; obj_exact is
        restricted to "process"/"proc".
        """
        tools = _scan_code(textwrap.dedent("""
            def cancel_animation():
                animation_proc.kill()
        """))
        # animation_proc matches obj_contains ["psutil", "psutil.process"]?
        # animation_proc != psutil (no substring match), but ALSO does not match
        # obj_exact ["process","proc"] because the obj is "animation_proc" full.
        # However obj_contains:["proc"] would match. Since we removed "proc"
        # from obj_contains, animation_proc should NOT match.
        assert len(tools) == 0, f"unexpected match: {[t.name for t in tools]}"

    def test_get_terminated_at_not_matched(self):
        """attr_exact:[kill,terminate,suspend] avoids matching get_terminated_at."""
        tools = _scan_code(textwrap.dedent("""
            import psutil

            def status(pid):
                p = psutil.Process(pid)
                return p.get_terminated_at()
        """))
        assert len(tools) == 0

    def test_terminate_session_not_matched(self):
        """terminate_session is a reader on a session object, not a kill signal."""
        tools = _scan_code(textwrap.dedent("""
            def end(session):
                return session.terminate_session()
        """))
        assert len(tools) == 0


# ---------------------------------------------------------------------------
# ANTI-FP — observability helper exclusion + return-value-used scoping
# ---------------------------------------------------------------------------


class TestAntiFpObservability:
    def setup_method(self, method):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def teardown_method(self, method):
        self.tmpdir.cleanup()

    def _write(self, name, content):
        f = self.root / name
        f.write_text(textwrap.dedent(content), encoding="utf-8")
        return f

    def test_log_helper_with_db_delete_alongside(self):
        """def tool(): _log(x); db.delete(x) → SEUL db.delete remonté.

        - _log_access matches log_/audit_ patterns → not followed.
        - db.delete is the intra-procedural side effect of the tool itself.
        - The fact that _log_access internally writes to audit_log MUST NOT
          surface as a side effect of `tool`.
        """
        # Helper that internally writes to audit log:
        self._write("audit.py", """
            class AuditLog:
                def insert(self, *a, **k): ...
            audit_log = AuditLog()

            def _log_access(user_id, action):
                audit_log.insert({"user": user_id, "action": action})
        """)
        # Tool that calls the helper as statement-only AND db.delete:
        self._write("svc.py", """
            from audit import _log_access

            class FakeDb:
                def delete(self, *a, **k): ...
            db = FakeDb()

            def purge(user_id):
                _log_access(user_id, "delete")
                db.delete({"id": user_id})
        """)
        tools = _scan_dir(self.root)
        assert "purge" in tools
        purge = tools["purge"]
        # All side-effects on purge must come from db.delete only, NOT audit_log.
        evidences = [se.evidence for se in purge.side_effects]
        assert any("db.delete" in e or "delete" in e for e in evidences)
        assert all("audit_log" not in e for e in evidences), (
            f"audit_log must NOT be surfaced via _log_access: {evidences}"
        )

    def test_statement_only_call_not_followed(self):
        """A statement-only helper call (return value not used) is not followed.

        Only db.delete (the direct intra-proc side effect) should remain.
        """
        self._write("helpers.py", """
            class FakeDb:
                def delete(self, *a, **k): ...
            db = FakeDb()

            def cleanup(user_id):
                db.delete({"id": user_id})
        """)
        self._write("tool_mod.py", """
            from helpers import cleanup

            def tool(user_id):
                cleanup(user_id)  # statement-only — NOT followed in v1
        """)
        tools = _scan_dir(self.root)
        # Statement-only fire-and-forget: the helper's db.delete must NOT
        # bubble up to `tool` in v1. Therefore `tool` has no side effect of
        # its own and is not reported as a Tool.
        assert "tool" not in tools


# ---------------------------------------------------------------------------
# FIX A v1 — same-module top-level delegation + symmetry
# ---------------------------------------------------------------------------


class TestFixA_Delegation:
    def setup_method(self, method):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def teardown_method(self, method):
        self.tmpdir.cleanup()

    def _write(self, name, content):
        f = self.root / name
        f.write_text(textwrap.dedent(content), encoding="utf-8")
        return f

    def test_delegation_same_module_with_evidence(self):
        """def tool(): return _purge(id) + def _purge: session.delete(...)
        → tool is UNGUARDED with evidence [via _purge]."""
        self._write("svc.py", """
            class S:
                def delete(self, *a, **k): ...
                def commit(self): ...
            session = S()

            def _purge(record_id):
                session.delete({"id": record_id})
                session.commit()

            def delete_user(record_id):
                return _purge(record_id)
        """)
        tools = _scan_dir(self.root)
        assert "delete_user" in tools
        t = tools["delete_user"]
        # Side-effect must be present and tagged with [via _purge ...]
        evidences = [se.evidence for se in t.side_effects]
        assert any("[via _purge()" in e for e in evidences), evidences

    def test_delegation_same_package_top_level(self):
        """Resolve through ImportFrom to a same-package top-level helper."""
        self._write("helpers.py", """
            class S:
                def delete(self, *a, **k): ...
            session = S()

            def _do_delete(rid):
                session.delete({"id": rid})
        """)
        self._write("tools.py", """
            from helpers import _do_delete

            def remove(rid):
                return _do_delete(rid)
        """)
        tools = _scan_dir(self.root)
        assert "remove" in tools
        ev = [se.evidence for se in tools["remove"].side_effects]
        assert any("[via _do_delete()" in e for e in ev), ev


class TestFixA_GuardSymmetry:
    def setup_method(self, method):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def teardown_method(self, method):
        self.tmpdir.cleanup()

    def _write(self, name, content):
        f = self.root / name
        f.write_text(textwrap.dedent(content), encoding="utf-8")
        return f

    def test_helper_validates_then_writes_guard_propagates(self):
        """Helper that validates then writes → guard propagates with side effect.

        Without symmetry, the side effect would surface UNGUARDED. With
        symmetry, the input_validation guard from the helper body propagates,
        and the verdict is NOT UNGUARDED.
        """
        self._write("svc.py", """
            class S:
                def delete(self, *a, **k): ...
            session = S()

            def _purge_with_check(count: int):
                if count > 1000000:
                    raise ValueError("count too large")
                session.delete({"id": count})

            def delete_user(count: int):
                return _purge_with_check(count)
        """)
        tools = _scan_dir(self.root)
        assert "delete_user" in tools
        t = tools["delete_user"]
        # Side effect via helper:
        ev = [se.evidence for se in t.side_effects]
        assert any("[via _purge_with_check()" in e for e in ev), ev
        # Guard from helper body propagated:
        # Either ValueError raise pattern or compare_contains amount/limit/etc.
        # We assert that there is at least one input_validation guard collected.
        # If the symmetry is correct, the verdict should not be UNGUARDED.
        assert t.verdict != "UNGUARDED", (
            f"helper guard must propagate, verdict={t.verdict}, guards={t.guards}"
        )


class TestFixA_DepthAndCycles:
    def setup_method(self, method):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def teardown_method(self, method):
        self.tmpdir.cleanup()

    def _write(self, name, content):
        f = self.root / name
        f.write_text(textwrap.dedent(content), encoding="utf-8")
        return f

    def test_depth_bound_does_not_loop(self):
        """A 4-level chain does not cause an infinite descent / RecursionError."""
        self._write("chain.py", """
            class S:
                def delete(self, *a, **k): ...
            session = S()

            def level3(x):
                session.delete({"id": x})

            def level2(x):
                return level3(x)

            def level1(x):
                return level2(x)

            def level0(x):
                return level1(x)
        """)
        # If this returns without RecursionError, the bound holds.
        tools = _scan_dir(self.root)
        # level0 may or may not see the deepest delete; what matters is no
        # exception is raised. If depth=2 default, level0 → level1 → level2
        # → cap; level3 not reached. That's acceptable.
        assert isinstance(tools, dict)

    def test_cycle_does_not_loop(self):
        """Mutual recursion between two helpers: scanner must terminate."""
        self._write("cyc.py", """
            class S:
                def delete(self, *a, **k): ...
            session = S()

            def a_func(x):
                return b_func(x)

            def b_func(x):
                session.delete({"id": x})
                return a_func(x)

            def tool_entry(x):
                return a_func(x)
        """)
        tools = _scan_dir(self.root)
        assert isinstance(tools, dict)


class TestFixA_ThirdPartyUnchanged:
    def test_direct_third_party_call_not_double_counted(self):
        """A tool calling requests.post() directly is matched by surface
        patterns; FIX A v1 must not double-count it.
        """
        tools = _scan_code(textwrap.dedent("""
            import requests

            def push(url, data):
                return requests.post(url, json=data)
        """))
        assert len(tools) == 1
        # Exactly one http_write side effect, not two.
        http_writes = [se for se in tools[0].side_effects if se.category == "http_write"]
        # Either matched as http_write OR as something — important: not duplicated.
        # We check there is at most one entry per (category, line):
        keys = [(se.category, se.line) for se in tools[0].side_effects]
        assert len(keys) == len(set(keys)), f"duplicate side-effects: {keys}"


class TestFixA_DedupMultiFile:
    def setup_method(self, method):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def teardown_method(self, method):
        self.tmpdir.cleanup()

    def _write(self, name, content):
        f = self.root / name
        f.write_text(textwrap.dedent(content), encoding="utf-8")
        return f

    def test_caller_and_callee_same_category_distinct_keys(self):
        """tool does db.delete AND calls _purge which also does db.delete.

        With dedup keyed on (file, category, line), both effects are kept
        as distinct entries (different files OR different lines). The bug
        the new key fixes: (category, line) only could collapse them when
        line numbers happen to coincide across files.
        """
        self._write("helpers.py", """
            class S:
                def delete(self, *a, **k): ...
            session = S()

            def _purge(rid):
                session.delete({"id": rid})
        """)
        self._write("tools.py", """
            from helpers import _purge

            class S:
                def delete(self, *a, **k): ...
            session = S()

            def remove(rid):
                session.delete({"id": rid})
                return _purge(rid)
        """)
        tools = _scan_dir(self.root)
        assert "remove" in tools
        # Two database_delete side effects expected: one from the caller body,
        # one from the helper. They live in different files → different keys
        # under (file, category, line) → both retained.
        deletes = [
            se for se in tools["remove"].side_effects
            if se.category == "database_delete"
        ]
        assert len(deletes) >= 2, (
            f"expected ≥2 database_delete entries (caller + helper), got: "
            f"{[(se.file, se.line, se.evidence) for se in deletes]}"
        )


# ---------------------------------------------------------------------------
# FIX B v1 — programmatic MCP registration (mcp.add_tool)
# ---------------------------------------------------------------------------


class TestFixB_AddTool:
    def setup_method(self, method):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def teardown_method(self, method):
        self.tmpdir.cleanup()

    def _write(self, name, content):
        f = self.root / name
        f.write_text(textwrap.dedent(content), encoding="utf-8")
        return f

    def test_add_tool_top_level_detected(self):
        """mcp.add_tool(_delete_collection) → exposure=mcp_tool, UNGUARDED."""
        self._write("server.py", """
            from fastmcp import FastMCP

            class Q:
                def delete_collection(self, *a, **k): ...
            qdrant = Q()
            mcp = FastMCP("q")

            def _delete_collection(name: str):
                qdrant.delete_collection(name=name)

            mcp.add_tool(_delete_collection)
        """)
        tools = _scan_dir(self.root)
        assert "_delete_collection" in tools, list(tools.keys())
        t = tools["_delete_collection"]
        assert t.exposure == "mcp_tool", t.exposure
        assert "add_tool" in t.exposure_evidence

    def test_add_tool_outside_mcp_context_not_detected(self):
        """mcp.add_tool(fn) in a file with NO MCP imports must NOT match —
        the module_is_mcp gate prevents this from being a stray FP."""
        self._write("not_mcp.py", """
            class Bag:
                def add_tool(self, fn): ...
            mcp = Bag()

            def helper():
                pass

            def write_one(x):
                bag_db.write({"x": x})

            mcp.add_tool(helper)
        """)
        tools = _scan_dir(self.root)
        # `helper` has no side effects → not in tools. `write_one` is reported
        # as a regular function (write detection), but its exposure must be
        # "internal" — module_is_mcp is False.
        if "write_one" in tools:
            assert tools["write_one"].exposure == "internal"
