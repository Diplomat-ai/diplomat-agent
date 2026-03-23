"""Tests for the analyzer module: verdicts and scenarios."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_canary.models import Guard, Scenario, SideEffect, Tool
from diplomat_canary.analyzer.guards import apply_verdicts, build_summary, compute_verdict
from diplomat_canary.analyzer.scenarios import generate_scenarios
from diplomat_canary.scanner.ast_scanner import scan_directory

FIXTURES = Path(__file__).parent / "fixtures"
CREWAI = FIXTURES / "crewai_agent"
RAW_PYTHON = FIXTURES / "raw_python_agent"


# ---------------------------------------------------------------------------
# Verdict computation on hand-crafted Tools
# ---------------------------------------------------------------------------


class TestComputeVerdict:
    def test_no_side_effects_is_low_risk(self):
        tool = Tool(name="reader", file="f.py", line=1, params=[],
                    side_effects=[], guards=[])
        assert compute_verdict(tool) == "LOW_RISK"

    def test_side_effects_no_guards_is_unguarded(self):
        tool = Tool(name="writer", file="f.py", line=1, params=[],
                    side_effects=[SideEffect(category="payment", evidence="x", line=2, file="f.py")],
                    guards=[])
        assert compute_verdict(tool) == "UNGUARDED"

    def test_partial_guard_is_partially_guarded(self):
        tool = Tool(name="writer", file="f.py", line=1, params=[],
                    side_effects=[SideEffect(category="database_write", evidence="x", line=2, file="f.py")],
                    guards=[Guard(type="input_validation", evidence="if x > 0", line=3, coverage="partial")])
        assert compute_verdict(tool) == "PARTIALLY_GUARDED"

    def test_full_guards_multiple_types_is_guarded(self):
        tool = Tool(name="writer", file="f.py", line=1, params=[],
                    side_effects=[SideEffect(category="payment", evidence="x", line=2, file="f.py")],
                    guards=[
                        Guard(type="input_validation", evidence="Field(le=1000)", line=3, coverage="full"),
                        Guard(type="rate_limit", evidence="@rate_limit", line=1, coverage="full"),
                    ])
        assert compute_verdict(tool) == "GUARDED"

    def test_one_full_guard_only_is_partially_guarded(self):
        tool = Tool(name="writer", file="f.py", line=1, params=[],
                    side_effects=[SideEffect(category="payment", evidence="x", line=2, file="f.py")],
                    guards=[
                        Guard(type="input_validation", evidence="Field(le=1000)", line=3, coverage="full"),
                    ])
        assert compute_verdict(tool) == "PARTIALLY_GUARDED"


class TestApplyVerdicts:
    def test_modifies_tools_in_place(self):
        tool = Tool(name="t", file="f.py", line=1, params=[],
                    side_effects=[SideEffect(category="payment", evidence="x", line=2, file="f.py")],
                    guards=[], verdict="UNGUARDED")
        result = apply_verdicts([tool])
        assert result[0] is tool
        assert tool.verdict == "UNGUARDED"

    def test_returns_same_list(self):
        tools = [
            Tool(name="a", file="f.py", line=1, params=[], side_effects=[], guards=[]),
            Tool(name="b", file="f.py", line=5, params=[],
                 side_effects=[SideEffect(category="email", evidence="x", line=6, file="f.py")],
                 guards=[]),
        ]
        result = apply_verdicts(tools)
        assert result is tools


class TestBuildSummary:
    def test_summary_counts(self):
        tools = [
            Tool(name="a", file="f.py", line=1, params=[], side_effects=[], guards=[], verdict="LOW_RISK"),
            Tool(name="b", file="f.py", line=5, params=[],
                 side_effects=[SideEffect(category="payment", evidence="x", line=6, file="f.py")],
                 guards=[], verdict="UNGUARDED"),
            Tool(name="c", file="f.py", line=10, params=[],
                 side_effects=[SideEffect(category="database_write", evidence="x", line=11, file="f.py")],
                 guards=[Guard(type="input_validation", evidence="if", line=10, coverage="partial")],
                 verdict="PARTIALLY_GUARDED"),
        ]
        summary = build_summary(tools)
        assert summary["total_tools"] == 3
        assert summary["unguarded"] == 1
        assert summary["partially_guarded"] == 1
        assert summary["low_risk"] == 1
        assert summary["guarded"] == 0


# ---------------------------------------------------------------------------
# Scenario generation
# ---------------------------------------------------------------------------


class TestGenerateScenarios:
    def test_no_scenarios_for_low_risk(self):
        tools = [Tool(name="reader", file="f.py", line=1, params=[],
                      side_effects=[], guards=[], verdict="LOW_RISK")]
        scenarios = generate_scenarios(tools)
        assert len(scenarios) == 0

    def test_scenarios_for_unguarded_payment(self):
        tools = [Tool(name="pay", file="f.py", line=1, params=[],
                      side_effects=[SideEffect(category="payment", evidence="x", line=2, file="f.py")],
                      guards=[], verdict="UNGUARDED")]
        scenarios = generate_scenarios(tools)
        assert len(scenarios) >= 1
        assert all(s.tool_name == "pay" for s in scenarios)
        assert any(s.risk_category == "financial" for s in scenarios)

    def test_scenarios_for_unguarded_database_delete(self):
        tools = [Tool(name="nuke", file="f.py", line=1, params=[],
                      side_effects=[SideEffect(category="database_delete", evidence="x", line=2, file="f.py")],
                      guards=[], verdict="UNGUARDED")]
        scenarios = generate_scenarios(tools)
        assert len(scenarios) >= 1
        assert any(s.risk_category == "data_loss" for s in scenarios)

    def test_partially_guarded_gets_fewer_scenarios(self):
        unguarded = [Tool(name="u", file="f.py", line=1, params=[],
                          side_effects=[SideEffect(category="payment", evidence="x", line=2, file="f.py")],
                          guards=[], verdict="UNGUARDED")]
        partial = [Tool(name="p", file="f.py", line=1, params=[],
                        side_effects=[SideEffect(category="payment", evidence="x", line=2, file="f.py")],
                        guards=[Guard(type="input_validation", evidence="if", line=3, coverage="partial")],
                        verdict="PARTIALLY_GUARDED")]
        sc_u = generate_scenarios(unguarded)
        sc_p = generate_scenarios(partial)
        assert len(sc_p) <= len(sc_u)

    def test_no_scenarios_for_guarded(self):
        tools = [Tool(name="safe", file="f.py", line=1, params=[],
                      side_effects=[SideEffect(category="payment", evidence="x", line=2, file="f.py")],
                      guards=[
                          Guard(type="input_validation", evidence="Field(le=1000)", line=3, coverage="full"),
                          Guard(type="rate_limit", evidence="@rate_limit", line=1, coverage="full"),
                      ], verdict="GUARDED")]
        scenarios = generate_scenarios(tools)
        assert len(scenarios) == 0


# ---------------------------------------------------------------------------
# Fixture-based tests: crewai_agent/agent.py
# ---------------------------------------------------------------------------


class TestCrewAIFixtureVerdicts:
    def setup_method(self):
        from diplomat_canary.scanner.ast_scanner import scan_file
        tools = scan_file(CREWAI / "agent.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_create_ticket_is_unguarded(self):
        assert "create_ticket" in self.tools
        assert self.tools["create_ticket"].verdict == "UNGUARDED"

    def test_escalate_to_human_has_auth_guard(self):
        assert "escalate_to_human" in self.tools
        guard_types = {g.type for g in self.tools["escalate_to_human"].guards}
        assert "auth_check" in guard_types

    def test_escalate_to_human_is_partially_guarded(self):
        assert self.tools["escalate_to_human"].verdict == "PARTIALLY_GUARDED"


# ---------------------------------------------------------------------------
# Fixture-based tests: raw_python_agent/services.py
# ---------------------------------------------------------------------------


class TestRawPythonServicesVerdicts:
    def setup_method(self):
        from diplomat_canary.scanner.ast_scanner import scan_file
        tools = scan_file(RAW_PYTHON / "services.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_make_payment_detected(self):
        assert "make_payment" in self.tools

    def test_make_payment_has_payment_side_effect(self):
        categories = {se.category for se in self.tools["make_payment"].side_effects}
        assert "payment" in categories

    def test_bulk_delete_is_unguarded(self):
        assert "bulk_delete" in self.tools
        assert self.tools["bulk_delete"].verdict == "UNGUARDED"

    def test_send_email_is_unguarded(self):
        assert "send_email" in self.tools
        assert self.tools["send_email"].verdict == "UNGUARDED"

    def test_send_email_has_email_side_effect(self):
        categories = {se.category for se in self.tools["send_email"].side_effects}
        assert "email" in categories
