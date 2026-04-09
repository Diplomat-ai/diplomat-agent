"""Tests for OWASP Agentic Top 10 mapping."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_agent.models import SideEffect, Tool
from diplomat_agent.analyzer.owasp import map_tool_to_owasp, apply_owasp


def _tool(categories: list[str], missing: list[str] | None = None) -> Tool:
    """Build a minimal Tool with given effect categories and missing hints."""
    effects = [
        SideEffect(category=cat, evidence="x", line=1, file="f.py")
        for cat in categories
    ]
    return Tool(
        name="test_fn", file="f.py", line=1, params=[],
        side_effects=effects,
        missing_hints=missing or [],
    )


class TestOWASPMapping:
    def test_payment_effect_maps_to_asi02_asi03(self):
        codes = map_tool_to_owasp(_tool(["payment"]))
        assert "ASI-02" in codes
        assert "ASI-03" in codes

    def test_missing_rate_limit_adds_asi06(self):
        codes = map_tool_to_owasp(_tool(["http_write"], ["no rate limit"]))
        assert "ASI-06" in codes

    def test_missing_auth_adds_asi01(self):
        codes = map_tool_to_owasp(_tool(["http_write"], ["no auth check"]))
        assert "ASI-01" in codes

    def test_agent_invocation_maps_to_asi04_asi10(self):
        codes = map_tool_to_owasp(_tool(["agent_invocation"]))
        assert "ASI-04" in codes
        assert "ASI-10" in codes

    def test_no_duplicates_in_output(self):
        codes = map_tool_to_owasp(_tool(["payment", "database_delete"]))
        assert len(codes) == len(set(codes))

    def test_empty_tool_returns_empty_list(self):
        codes = map_tool_to_owasp(_tool([]))
        assert codes == []

    def test_llm_call_maps_to_asi05(self):
        codes = map_tool_to_owasp(_tool(["llm_call"]))
        assert "ASI-05" in codes

    def test_dynamic_code_maps_to_asi03(self):
        codes = map_tool_to_owasp(_tool(["dynamic_code"]))
        assert "ASI-03" in codes

    def test_results_are_sorted(self):
        codes = map_tool_to_owasp(_tool(["agent_invocation"], ["no auth check"]))
        assert codes == sorted(codes)

    def test_apply_owasp_populates_field(self):
        tools = [_tool(["payment"]), _tool(["http_write"], ["no rate limit"])]
        apply_owasp(tools)
        assert tools[0].owasp_agentic == ["ASI-02", "ASI-03"]
        assert "ASI-06" in tools[1].owasp_agentic
