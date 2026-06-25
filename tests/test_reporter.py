"""Tests for the reporter module: terminal and JSON output."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_agent.models import Guard, Scenario, ScanResult, SideEffect, Tool
from diplomat_agent.reporter.terminal import render_plain
from diplomat_agent.reporter.json_report import render_json
from diplomat_agent.analyzer.guards import apply_verdicts, build_summary
from diplomat_agent.analyzer.scenarios import generate_scenarios
from diplomat_agent.scanner.ast_scanner import scan_directory

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
        assert "diplomat-agent" in output

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
        for key in ("scanned_path", "summary", "findings", "version"):
            assert key in data

    def test_json_tools_count(self):
        result = _make_handcrafted_result()
        output = render_json(result, "./test/")
        data = json.loads(output)
        assert len(data["findings"]) == 2

    def test_json_summary_integrity(self):
        result = _make_handcrafted_result()
        output = render_json(result, "./test/")
        data = json.loads(output)
        s = data["summary"]
        total = s["unguarded"] + s["partially_guarded"] + s["guarded"] + s["low_risk"]
        assert s["total"] == total

    def test_json_finding_has_required_fields(self):
        result = _make_handcrafted_result()
        output = render_json(result, "./test/")
        data = json.loads(output)
        if data["findings"]:
            f = data["findings"][0]
            for field in ("function", "file", "line", "actions", "checks", "missing", "verdict"):
                assert field in f

    def test_json_finding_includes_exposure(self):
        """GATE 3 — every finding must carry the exposure tag."""
        result = _make_handcrafted_result()
        output = render_json(result, "./test/")
        data = json.loads(output)
        for f in data["findings"]:
            assert "exposure" in f, (
                f"finding missing 'exposure' field: {f}"
            )

    def test_json_finding_serializes_opaque_reason(self):
        """GATE 3 — opaque_reason is serialized when non-empty."""
        from diplomat_agent.models import ScanResult, Tool
        tool = Tool(
            name="proxy",
            file="x.py",
            line=1,
            params=[],
            side_effects=[],
            guards=[],
            verdict="OPAQUE",
            exposure="mcp_client",
            opaque_reason="mcp_client proxy: remote tool semantics not in scan unit",
        )
        result = ScanResult(tools=[tool], summary={"total_tools": 1}, scenarios=[])
        data = json.loads(render_json(result, "./x/"))
        f = data["findings"][0]
        assert f.get("opaque_reason") == (
            "mcp_client proxy: remote tool semantics not in scan unit"
        )
        assert f["exposure"] == "mcp_client"

    def test_json_finding_omits_empty_opaque_reason(self):
        """GATE 3 — opaque_reason key is omitted when empty (compact output)."""
        result = _make_handcrafted_result()
        output = render_json(result, "./test/")
        data = json.loads(output)
        for f in data["findings"]:
            if "opaque_reason" in f:
                assert f["opaque_reason"], (
                    "opaque_reason key present but empty — should be omitted"
                )


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


# ---------------------------------------------------------------------------
# Guard label deduplication
# ---------------------------------------------------------------------------


class TestGuardLabelDedup:
    """Rate limit: NONE must not appear twice when http_write + database_write coexist."""

    def test_rate_limit_not_duplicated(self):
        tool = Tool(
            name="research_and_save",
            file="test.py",
            line=1,
            params=[],
            side_effects=[
                SideEffect(category="http_write", evidence="requests.post(...)", line=2, file="test.py", type="http_write"),
                SideEffect(category="database_write", evidence="conn.commit()", line=3, file="test.py", type="database_write"),
            ],
            guards=[],
            verdict="UNGUARDED",
        )
        result = ScanResult(
            tools=[tool],
            scenarios=[],
            summary={"total_tools": 1, "unguarded": 1, "partially_guarded": 0, "guarded": 0, "low_risk": 0},
        )
        output = render_plain(result, "/tmp/test")
        count = output.count("Rate limit:")
        assert count == 1, f"Expected 'Rate limit:' once, found {count} times"

    def test_confirmation_not_duplicated(self):
        tool = Tool(
            name="cleanup",
            file="test.py",
            line=1,
            params=[],
            side_effects=[
                SideEffect(category="file_delete", evidence="os.remove(f)", line=2, file="test.py", type="file_delete"),
                SideEffect(category="destructive", evidence="subprocess.run(cmd)", line=3, file="test.py", type="destructive"),
            ],
            guards=[],
            verdict="UNGUARDED",
        )
        result = ScanResult(
            tools=[tool],
            scenarios=[],
            summary={"total_tools": 1, "unguarded": 1, "partially_guarded": 0, "guarded": 0, "low_risk": 0},
        )
        output = render_plain(result, "/tmp/test")
        count = output.count("Confirmation step:")
        assert count == 1, f"Expected 'Confirmation step:' once, found {count} times"
