"""Tests for MCP server tool exposure detection (SPEC-FEAT-MCP-SCAN-v1)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_agent.scanner.ast_scanner import scan_file
from diplomat_agent.scanner.interprocedural import PackageIndex
from diplomat_agent.analyzer.guards import apply_verdicts

MCP_FIXTURES = Path(__file__).parent / "fixtures" / "mcp"


# ---------------------------------------------------------------------------
# 1. FastMCP official SDK — unguarded tool
# ---------------------------------------------------------------------------


class TestMcpServerUnguarded:
    def setup_method(self):
        tools = scan_file(MCP_FIXTURES / "server_unguarded.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_wipe_detected(self):
        assert "wipe" in self.tools

    def test_wipe_exposure_is_mcp_tool(self):
        assert self.tools["wipe"].exposure == "mcp_tool"

    def test_wipe_verdict_is_unguarded(self):
        assert self.tools["wipe"].verdict == "UNGUARDED"

    def test_wipe_evidence_contains_at(self):
        assert "@" in self.tools["wipe"].exposure_evidence


# ---------------------------------------------------------------------------
# 2. FastMCP official SDK — guarded tool
# ---------------------------------------------------------------------------


class TestMcpServerGuarded:
    def setup_method(self):
        tools = scan_file(MCP_FIXTURES / "server_guarded.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_delete_old_records_detected(self):
        assert "delete_old_records" in self.tools

    def test_delete_old_records_exposure_is_mcp_tool(self):
        assert self.tools["delete_old_records"].exposure == "mcp_tool"

    def test_delete_old_records_verdict_is_guarded_or_partial(self):
        # Numeric bounds check → input_validation guard.
        # database_delete also expects approval_step → PARTIALLY_GUARDED at minimum.
        assert self.tools["delete_old_records"].verdict in ("GUARDED", "PARTIALLY_GUARDED")


# ---------------------------------------------------------------------------
# 3. FastMCP v2 standalone import (from fastmcp import FastMCP)
# ---------------------------------------------------------------------------


class TestMcpFastmcpV2:
    def setup_method(self):
        tools = scan_file(MCP_FIXTURES / "server_fastmcp_v2.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_remove_entry_detected(self):
        assert "remove_entry" in self.tools

    def test_remove_entry_exposure_is_mcp_tool(self):
        """fastmcp standalone import must trigger the MCP gate."""
        assert self.tools["remove_entry"].exposure == "mcp_tool"

    def test_remove_entry_verdict_is_unguarded(self):
        assert self.tools["remove_entry"].verdict == "UNGUARDED"


# ---------------------------------------------------------------------------
# 4. Import gate — @something.tool WITHOUT MCP import
# ---------------------------------------------------------------------------


class TestMcpImportGate:
    def setup_method(self):
        tools = scan_file(MCP_FIXTURES / "not_mcp.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_remove_stuff_detected(self):
        """Side effect (os.remove) is present, tool must be detected."""
        assert "remove_stuff" in self.tools

    def test_remove_stuff_exposure_is_internal(self):
        """No MCP import → @something.tool must NOT be tagged as mcp_tool."""
        assert self.tools["remove_stuff"].exposure == "internal"


# ---------------------------------------------------------------------------
# 5. Low-level @server.call_tool() dispatcher
# ---------------------------------------------------------------------------


class TestMcpLowLevel:
    def setup_method(self):
        tools = scan_file(MCP_FIXTURES / "lowlevel.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_handle_tool_detected(self):
        """Zero-branch dispatcher must surface (GATE 2 fallback)."""
        assert "handle_tool" in self.tools

    def test_handle_tool_exposure_is_mcp_internal(self):
        """@server.call_tool dispatcher with no resolvable branches keeps
        exposure='mcp_internal' (GATE 6 classification)."""
        assert self.tools["handle_tool"].exposure == "mcp_internal"

    def test_handle_tool_verdict_is_opaque(self):
        """GATE 2: dispatcher with zero branches must be OPAQUE — per-tool
        semantics are unknown, honesty floor applies."""
        assert self.tools["handle_tool"].verdict == "OPAQUE"

    def test_handle_tool_opaque_reason_mentions_dispatcher(self):
        assert "dispatcher" in self.tools["handle_tool"].opaque_reason


# ---------------------------------------------------------------------------
# 6. GATE 1 — étage 1 OPAQUE floor for unresolved effect-carriers
# ---------------------------------------------------------------------------


class TestWrappedDbToolOpaque:
    def setup_method(self):
        tools = scan_file(MCP_FIXTURES / "wrapped_db_tool.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_run_query_detected(self):
        assert "run_query" in self.tools

    def test_run_query_verdict_is_opaque(self):
        assert self.tools["run_query"].verdict == "OPAQUE"

    def test_run_query_opaque_reason_mentions_vault_action(self):
        assert "vault_action" in self.tools["run_query"].opaque_reason

    def test_run_query_exposure_is_mcp_tool(self):
        assert self.tools["run_query"].exposure == "mcp_tool"


class TestWrappedSocketToolOpaque:
    def setup_method(self):
        tools = scan_file(MCP_FIXTURES / "wrapped_socket_tool.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_do_thing_detected(self):
        assert "do_thing" in self.tools

    def test_do_thing_verdict_is_opaque(self):
        assert self.tools["do_thing"].verdict == "OPAQUE"

    def test_do_thing_opaque_reason_mentions_vault_transfer(self):
        assert "vault_transfer" in self.tools["do_thing"].opaque_reason


class TestPureToolNotOpaque:
    """GATE 1 negative: pure @mcp.tool with no external calls must NOT be OPAQUE."""

    def setup_method(self):
        tools = scan_file(MCP_FIXTURES / "pure_tool.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_add_not_opaque(self):
        # Either dropped entirely (no side effect) or surfaced as non-OPAQUE.
        if "add" in self.tools:
            assert self.tools["add"].verdict != "OPAQUE"


class TestReadonlyLoggingToolNotOpaque:
    """GATE 1 negative: read-only logging tool must NOT be OPAQUE."""

    def setup_method(self):
        tools = scan_file(MCP_FIXTURES / "readonly_logging_tool.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_status_not_opaque(self):
        if "status" in self.tools:
            assert self.tools["status"].verdict != "OPAQUE"


# ---------------------------------------------------------------------------
# 7. GATE 4 — dynamic registration mcp.tool(name=...)(fn)
# ---------------------------------------------------------------------------


class TestEtage2SelfMethod:
    """GATE 5: self.method() inside a class must resolve to the enclosing
    class method via lookup_class_method, surfacing the real side effect."""

    def setup_method(self):
        fixture = MCP_FIXTURES / "etage2_self_method.py"
        pkg = PackageIndex(fixture.parent)
        tools = scan_file(fixture, package_index=pkg)
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_run_detected(self):
        assert "run" in self.tools

    def test_run_exposure_is_mcp_tool(self):
        assert self.tools["run"].exposure == "mcp_tool"

    def test_run_verdict_is_unguarded(self):
        """Étage 2 resolution must surface os.remove → UNGUARDED, not OPAQUE."""
        assert self.tools["run"].verdict == "UNGUARDED"

    def test_run_side_effects_mention_remove(self):
        evidence = " ".join(se.evidence for se in self.tools["run"].side_effects)
        assert "remove" in evidence


class TestEtage2ClassMethod:
    """GATE 5: PascalCase receiver Writer.method() resolves to enclosing
    class method via the type heuristic."""

    def setup_method(self):
        fixture = MCP_FIXTURES / "etage2_class_method.py"
        pkg = PackageIndex(fixture.parent)
        tools = scan_file(fixture, package_index=pkg)
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_run_detected(self):
        assert "run" in self.tools

    def test_run_verdict_is_unguarded(self):
        assert self.tools["run"].verdict == "UNGUARDED"

    def test_run_side_effects_mention_remove(self):
        evidence = " ".join(se.evidence for se in self.tools["run"].side_effects)
        assert "remove" in evidence


class TestEtage2LocalBinding:
    """GATE 5: `w = Writer()` plain assign in the function body binds w to
    Writer, letting étage 2 resolve w.run(path) → Writer.run."""

    def setup_method(self):
        fixture = MCP_FIXTURES / "etage2_local_binding.py"
        pkg = PackageIndex(fixture.parent)
        tools = scan_file(fixture, package_index=pkg)
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_handler_detected(self):
        assert "handler" in self.tools

    def test_handler_verdict_is_unguarded(self):
        assert self.tools["handler"].verdict == "UNGUARDED"

    def test_handler_side_effects_mention_remove(self):
        evidence = " ".join(se.evidence for se in self.tools["handler"].side_effects)
        assert "remove" in evidence


class TestGate6SdkVerbs:
    """GATE 6: narrow SDK verbs (execute_query, sendall, send_command,
    start_execution, execute_param_query) recognised on any receiver."""

    def setup_method(self):
        tools = scan_file(MCP_FIXTURES / "gate6_sdk_verbs.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_do_query_unguarded(self):
        assert self.tools["do_query"].verdict == "UNGUARDED"

    def test_do_param_query_unguarded(self):
        assert self.tools["do_param_query"].verdict == "UNGUARDED"

    def test_do_sendall_unguarded(self):
        assert self.tools["do_sendall"].verdict == "UNGUARDED"

    def test_do_send_command_unguarded(self):
        assert self.tools["do_send_command"].verdict == "UNGUARDED"

    def test_do_start_execution_unguarded(self):
        assert self.tools["do_start_execution"].verdict == "UNGUARDED"


class TestDynamicRegistration:
    def setup_method(self):
        tools = scan_file(MCP_FIXTURES / "dynamic_registration_tool.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_lambda_function_detected(self):
        assert "lambda_function" in self.tools

    def test_lambda_function_exposure_is_mcp_tool(self):
        """Curried registration mcp.tool(name=...)(fn) must promote the
        registered function to exposure='mcp_tool'."""
        assert self.tools["lambda_function"].exposure == "mcp_tool"

    def test_lambda_function_verdict_is_unguarded(self):
        """os.remove inside the registered function → UNGUARDED."""
        assert self.tools["lambda_function"].verdict == "UNGUARDED"

    def test_lambda_function_evidence_mentions_programmatic(self):
        assert "programmatic" in self.tools["lambda_function"].exposure_evidence
