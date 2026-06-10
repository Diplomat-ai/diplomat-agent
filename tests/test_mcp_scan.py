"""Tests for MCP server tool exposure detection (SPEC-FEAT-MCP-SCAN-v1)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_agent.scanner.ast_scanner import scan_file
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
        """Dispatcher body has os.remove → detected as tool with side effect."""
        assert "handle_tool" in self.tools

    def test_handle_tool_exposure_is_mcp_internal(self):
        """@server.call_tool dispatcher in an MCP module whose branches cannot be resolved
        keeps exposure='mcp_internal' (reclassified from 'internal' by GATE 6)."""
        assert self.tools["handle_tool"].exposure == "mcp_internal"
