"""Tests for the SARIF 2.1.0 reporter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_agent.models import Guard, ScanResult, SideEffect, Tool
from diplomat_agent.analyzer.guards import apply_verdicts, build_summary
from diplomat_agent.analyzer.scenarios import generate_scenarios
from diplomat_agent.analyzer.owasp import apply_owasp
from diplomat_agent.reporter.sarif import generate_sarif, render_sarif


def _make_result() -> ScanResult:
    """Build a minimal ScanResult with varied verdicts."""
    tools = [
        Tool(
            name="process_refund", file="tools.py", line=10,
            params=[{"name": "amount", "type": "float", "has_bounds": False}],
            side_effects=[SideEffect(category="payment", evidence="stripe.Refund.create()", line=12, file="tools.py")],
            guards=[],
        ),
        Tool(
            name="update_record", file="api/routes.py", line=88,
            params=[],
            side_effects=[SideEffect(category="database_write", evidence="session.commit()", line=90, file="api/routes.py")],
            guards=[Guard(type="auth_check", evidence="Depends(get_current_user)", line=89, coverage="partial")],
        ),
        Tool(
            name="get_status", file="tools.py", line=50,
            params=[],
            side_effects=[], guards=[],
        ),
    ]
    apply_verdicts(tools)
    from diplomat_agent.analyzer.checks import apply_missing_hints
    apply_missing_hints(tools)
    apply_owasp(tools)
    scenarios = generate_scenarios(tools)
    summary = build_summary(tools)
    return ScanResult(tools=tools, scenarios=scenarios, summary=summary)


class TestSARIF:
    def test_sarif_valid_json_structure(self):
        result = _make_result()
        sarif = generate_sarif(result)
        assert sarif["version"] == "2.1.0"
        assert "$schema" in sarif
        assert len(sarif["runs"]) == 1
        run = sarif["runs"][0]
        assert "tool" in run
        assert "results" in run
        assert run["tool"]["driver"]["name"] == "diplomat-agent"

    def test_sarif_rules_match_findings(self):
        result = _make_result()
        sarif = generate_sarif(result)
        run = sarif["runs"][0]
        rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
        result_rule_ids = {r["ruleId"] for r in run["results"]}
        # Every result ruleId should have a corresponding rule
        assert result_rule_ids <= rule_ids

    def test_sarif_has_stable_rule_ids(self):
        result = _make_result()
        sarif = generate_sarif(result)
        rule_ids = {r["id"] for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
        # process_refund → DA004 (payment), update_record → DA009 (partially guarded)
        assert rule_ids <= {"DA001", "DA002", "DA003", "DA004", "DA005", "DA006", "DA007", "DA008", "DA009"}

    def test_sarif_levels_match_verdicts(self):
        result = _make_result()
        sarif = generate_sarif(result)
        results = sarif["runs"][0]["results"]
        for r in results:
            assert r["level"] in ("error", "warning", "none")
        # process_refund is UNGUARDED → error
        payment_results = [r for r in results if "process_refund" in r["message"]["text"]]
        assert payment_results[0]["level"] == "error"
        # update_record is PARTIALLY_GUARDED → warning
        db_results = [r for r in results if "update_record" in r["message"]["text"]]
        assert db_results[0]["level"] == "warning"

    def test_sarif_locations_have_file_and_line(self):
        result = _make_result()
        sarif = generate_sarif(result)
        for r in sarif["runs"][0]["results"]:
            loc = r["locations"][0]["physicalLocation"]
            assert "artifactLocation" in loc
            assert "uri" in loc["artifactLocation"]
            assert "region" in loc
            assert "startLine" in loc["region"]

    def test_sarif_low_risk_excluded(self):
        result = _make_result()
        sarif = generate_sarif(result)
        results = sarif["runs"][0]["results"]
        for r in results:
            assert "get_status" not in r["message"]["text"]

    def test_render_sarif_returns_valid_json(self):
        result = _make_result()
        text = render_sarif(result)
        parsed = json.loads(text)
        assert parsed["version"] == "2.1.0"

    def test_sarif_always_emits_9_rules(self):
        """driver.rules must always contain DA001-DA009 regardless of findings."""
        result = _make_result()
        sarif = generate_sarif(result)
        rule_ids = sorted([r["id"] for r in sarif["runs"][0]["tool"]["driver"]["rules"]])
        expected = ["DA001", "DA002", "DA003", "DA004", "DA005", "DA006", "DA007", "DA008", "DA009"]
        assert rule_ids == expected

    def test_sarif_rules_have_required_fields(self):
        """Each rule must have id, name, shortDescription, defaultConfiguration, helpUri."""
        result = _make_result()
        sarif = generate_sarif(result)
        for rule in sarif["runs"][0]["tool"]["driver"]["rules"]:
            assert "id" in rule
            assert "name" in rule
            assert "shortDescription" in rule
            assert "defaultConfiguration" in rule
            assert "helpUri" in rule

    def test_sarif_9_rules_with_empty_scan(self):
        """Even with zero findings, all 9 rules must be present."""
        empty = ScanResult(tools=[], scenarios=[], summary=build_summary([]))
        sarif = generate_sarif(empty)
        rule_ids = sorted([r["id"] for r in sarif["runs"][0]["tool"]["driver"]["rules"]])
        expected = ["DA001", "DA002", "DA003", "DA004", "DA005", "DA006", "DA007", "DA008", "DA009"]
        assert rule_ids == expected
        assert sarif["runs"][0]["results"] == []

    def test_sarif_rules_stable_across_scans(self):
        """Same rules emitted for different scan contents."""
        full = _make_result()
        empty = ScanResult(tools=[], scenarios=[], summary=build_summary([]))
        sarif_full = generate_sarif(full)
        sarif_empty = generate_sarif(empty)
        rules1 = sorted([r["id"] for r in sarif_full["runs"][0]["tool"]["driver"]["rules"]])
        rules2 = sorted([r["id"] for r in sarif_empty["runs"][0]["tool"]["driver"]["rules"]])
        assert rules1 == rules2
