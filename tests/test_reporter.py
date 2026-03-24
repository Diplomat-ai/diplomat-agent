"""Tests for the reporter module: terminal and JSON output."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat.models import Guard, Scenario, ScanResult, SideEffect, Tool
from diplomat.reporter.terminal import render_plain
from diplomat.reporter.json_report import render_json
from diplomat.analyzer.guards import apply_verdicts, build_summary
from diplomat.analyzer.scenarios import generate_scenarios
from diplomat.scanner.ast_scanner import scan_directory

FIXTURES = Path(__file__).parent / "fixtures"


def _make_result_from_dir(directory: Path) -> ScanResult:
    tools = scan_directory(directory)
    apply_verdicts(tools)
    scenarios = generate_scenarios(tools)
    summary = build_summary(tools)
    return ScanResult(tools=tools, scenarios=scenarios, summary=summary)


def _make_handcrafted_result() -> ScanResult:
    """Build a minimal ScanResult by hand for predictable assertions."""
    tools = [
        Tool(name="process_refund", file="tools.py", line=10,
             params=[{"name": "amount", "type": "float", "has_bounds": False}],
             side_effects=[SideEffect(category="payment", evidence="stripe.Refund.create()", line=12, file="tools.py")],
             guards=[], verdict="UNGUARDED"),
        Tool(name="get_status", file="tools.py", line=50,
             params=[{"name": "id", "type": "str", "has_bounds": False}],
             side_effects=[], guards=[], verdict="LOW_RISK"),
    ]
    scenarios = generate_scenarios(tools)
    summary = build_summary(tools)
    return ScanResult(tools=tools, scenarios=scenarios, summary=summary)


# ---------------------------------------------------------------------------
# Terminal reporter
# ---------------------------------------------------------------------------


class TestRenderPlain:
    def test_header_present(self):
        result = _make_handcrafted_result()
        output = render_plain(result, "./test/")
        assert "diplomat" in output

    def test_scanned_path_present(self):
        result = _make_handcrafted_result()
        output = render_plain(result, "./my_project/")
        assert "./my_project/" in output

    def test_cta_last_line(self):
        result = _make_handcrafted_result()
        output = render_plain(result, "./test/")
        non_empty = [line for line in output.strip().splitlines() if line.strip()]
        assert "--fail-on-unchecked" in non_empty[-1]

    def test_warning_icon_for_unguarded(self):
        result = _make_handcrafted_result()
        output = render_plain(result, "./test/")
        assert "⚠" in output

    def test_check_icon_for_low_risk(self):
        result = _make_handcrafted_result()
        output = render_plain(result, "./test/")
        assert "✓" in output

    def test_read_only_label_for_low_risk(self):
        result = _make_handcrafted_result()
        output = render_plain(result, "./test/")
        assert "Read-only:" in output
        assert "YES" in output

    def test_result_line_present(self):
        result = _make_handcrafted_result()
        output = render_plain(result, "./test/")
        assert "RESULT:" in output

    def test_guard_lines_for_payment(self):
        result = _make_handcrafted_result()
        output = render_plain(result, "./test/")
        assert "Bounds on amount:" in output
        assert "Rate limit:" in output
        assert "Approval step:" in output

    def test_exposure_line_present(self):
        result = _make_handcrafted_result()
        output = render_plain(result, "./test/")
        assert "Estimated exposure:" in output


# ---------------------------------------------------------------------------
# JSON reporter
# ---------------------------------------------------------------------------


class TestRenderJson:
    def test_valid_json(self):
        result = _make_handcrafted_result()
        output = render_json(result, "./test/")
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_json_has_all_keys(self):
        result = _make_handcrafted_result()
        output = render_json(result, "./test/")
        data = json.loads(output)
        for key in ("scanned_path", "summary", "tools", "scenarios"):
            assert key in data

    def test_json_tools_count(self):
        result = _make_handcrafted_result()
        output = render_json(result, "./test/")
        data = json.loads(output)
        assert len(data["tools"]) == 2

    def test_json_summary_integrity(self):
        result = _make_handcrafted_result()
        output = render_json(result, "./test/")
        data = json.loads(output)
        s = data["summary"]
        total = s["unguarded"] + s["partially_guarded"] + s["guarded"] + s["low_risk"]
        assert s["total_tools"] == total

    def test_json_scenario_has_required_fields(self):
        result = _make_handcrafted_result()
        output = render_json(result, "./test/")
        data = json.loads(output)
        if data["scenarios"]:
            sc = data["scenarios"][0]
            for field in ("tool_name", "description", "risk_category", "estimated_impact"):
                assert field in sc


# ---------------------------------------------------------------------------
# Full pipeline through fixtures
# ---------------------------------------------------------------------------


class TestFullPipelineReport:
    def test_crewai_report_mentions_create_ticket(self):
        result = _make_result_from_dir(FIXTURES / "crewai_agent")
        output = render_plain(result, "./crewai/")
        assert "create_ticket" in output

    def test_raw_python_report_mentions_bulk_delete(self):
        result = _make_result_from_dir(FIXTURES / "raw_python_agent")
        output = render_plain(result, "./raw/")
        assert "bulk_delete" in output
