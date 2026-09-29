"""GATE A3 — ``--emit-gate-config``: a diplomat-gate config derived from real
scan results, loadable by ``diplomat_gate.Gate.from_yaml()``.

These tests import diplomat-gate's real loader to load the generated YAML,
matching the spec's own acceptance command
(``from diplomat_gate import Gate; Gate.from_yaml(...)``). diplomat-gate is
NOT a dependency of this repo (zero-dependency rule, same reasoning as
GATE A2's hardcoded policy-id snapshot): every ``Gate.from_yaml`` assertion
below is preceded by ``pytest.importorskip("diplomat_gate")`` so this suite
still passes in diplomat-agent's own CI, where diplomat-gate is not
installed, and only exercises the real cross-repo load where it is (e.g. a
developer's machine with both repos checked out, or a dedicated integration
job). They do not check the loaded policy *behavior*, only that the file is
structurally valid and that no invented policy id ever appears in it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from diplomat_agent.models import ScanResult, SideEffect, Tool
from diplomat_agent.reporter.gate_config import generate
from diplomat_agent.reporter.gate_mapping import GATE_FAMILY_MAP

REPO = Path(__file__).parent.parent
FIXTURES = REPO / "tests" / "fixtures"

# Every policy id GATE_FAMILY_MAP is allowed to suggest (mirrors
# tests/test_gate_mapping.py's hardcoded snapshot of diplomat-gate's
# _POLICY_MAP keys, diplomat-gate@63dfa8c).
GATE_POLICY_IDS = {
    "payment.amount_limit",
    "payment.velocity",
    "payment.daily_limit",
    "payment.duplicate_detection",
    "payment.recipient_blocklist",
    "email.domain_blocklist",
    "email.rate_limit",
    "email.business_hours",
    "email.content_scan",
}


def _tool(name: str, categories: list[str]) -> Tool:
    effects = [
        SideEffect(category=c, evidence="x()", line=1, file=f"{name}.py") for c in categories
    ]
    return Tool(name=name, file=f"{name}.py", line=1, params=[], side_effects=effects)


def _result(tools: list[Tool]) -> ScanResult:
    return ScanResult(tools=tools, scenarios=[], summary={})


def _emitted_ids(yaml_text: str) -> list[str]:
    return re.findall(r"^\s*-\s*id:\s*(\S+)", yaml_text, re.MULTILINE)


class TestPositive:
    def test_mixed_fixture_loads_with_two_active_families(self, tmp_path):
        from diplomat_agent.scanner.ast_scanner import scan_directory

        tools = scan_directory(FIXTURES / "gate_config_mixed")
        result = _result(tools)
        out = tmp_path / "gen.yaml"
        content = generate(
            result, output_path=out, scanned_path=str(FIXTURES / "gate_config_mixed")
        )
        assert out.read_text(encoding="utf-8") == content

        pytest.importorskip("diplomat_gate")
        from diplomat_gate import Gate

        gate = Gate.from_yaml(str(out))
        assert len(gate.policies) == 4
        families = {p.policy_id.split(".")[0] for p in gate.policies}
        assert families == {"payment", "email"}
        assert all(p.on_fail == "REVIEW" for p in gate.policies)


class TestNegative:
    def test_no_side_effects_produces_valid_empty_policies(self, tmp_path):
        result = _result([_tool("add", [])])
        out = tmp_path / "gen.yaml"
        content = generate(result, output_path=out, scanned_path=".")
        assert "policies: []" in content
        assert "#" in content  # explicit comment, not a bare empty file

        pytest.importorskip("diplomat_gate")
        from diplomat_gate import Gate

        gate = Gate.from_yaml(str(out))
        assert gate.policies == []

    def test_only_unimplemented_categories_produces_no_active_policy(self, tmp_path):
        result = _result([_tool("cleanup", ["file_delete"])])
        out = tmp_path / "gen.yaml"
        content = generate(result, output_path=out, scanned_path=".")
        assert "policies: []" in content
        assert "file_delete" in content
        assert "issues/12" in content  # GATE_FAMILY_MAP["file_delete"].issue == 12

        pytest.importorskip("diplomat_gate")
        from diplomat_gate import Gate

        gate = Gate.from_yaml(str(out))
        assert gate.policies == []

    def test_never_emits_a_policy_id_absent_from_gate_family_map(self, tmp_path):
        """Every id: line must be one of the suggested ids in GATE_FAMILY_MAP —
        never invented, never a phantom category's id."""
        all_categories = list(GATE_FAMILY_MAP)
        result = _result([_tool(f"t_{c}", [c]) for c in all_categories])
        out = tmp_path / "gen.yaml"
        content = generate(result, output_path=out, scanned_path=".")

        emitted = _emitted_ids(content)
        assert emitted, "expected at least one policy id in this all-categories fixture"
        allowed = {pid for fam in GATE_FAMILY_MAP.values() for pid in fam.suggested}
        for policy_id in emitted:
            assert policy_id in allowed
            assert policy_id in GATE_POLICY_IDS

        pytest.importorskip("diplomat_gate")
        from diplomat_gate import Gate

        gate = Gate.from_yaml(str(out))
        assert len(gate.policies) == len(emitted)
