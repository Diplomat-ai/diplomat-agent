"""Tests for the registry reporter (toolcalls.yaml) and related features."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_agent.scanner.ast_scanner import scan_directory
from diplomat_agent.analyzer.guards import apply_verdicts, build_summary
from diplomat_agent.analyzer.scenarios import generate_scenarios
from diplomat_agent.analyzer.checks import apply_missing_hints
from diplomat_agent.models import ScanResult
from diplomat_agent.reporter.registry import generate, load_baseline

FIXTURES = Path(__file__).parent / "fixtures"
LANGGRAPH = FIXTURES / "langgraph_agent"
CHECKED_OK = FIXTURES / "checked_ok_agent"


def _scan_and_build(fixture_path: Path) -> ScanResult:
    """Scan a fixture dir and return a full ScanResult."""
    tools = scan_directory(fixture_path)
    apply_verdicts(tools)
    apply_missing_hints(tools)
    scenarios = generate_scenarios(tools)
    summary = build_summary(tools)
    return ScanResult(tools=tools, scenarios=scenarios, summary=summary)


# ---------------------------------------------------------------------------
# 1. Registry generation produces valid YAML with correct structure
# ---------------------------------------------------------------------------


class TestRegistryGeneration:
    def test_registry_generation(self, tmp_path):
        """Scan a fixture → YAML valid, correct sections, correct summary."""
        result = _scan_and_build(LANGGRAPH)
        out = tmp_path / "toolcalls.yaml"
        content = generate(result, output_path=out, scanned_path=str(LANGGRAPH))

        assert out.exists()
        assert "generated:" in content
        assert "version:" in content
        assert "summary:" in content
        assert "tool_calls:" in content

        # Check each entry has required fields
        assert "function:" in content
        assert "file:" in content
        assert "line:" in content
        assert "actions:" in content
        assert "checks:" in content
        assert "missing:" in content

        # Must NOT have owner, reviewed, resolve fields
        assert "owner:" not in content
        assert "reviewed:" not in content
        assert "resolve:" not in content

        # Validate YAML if pyyaml is available
        try:
            import yaml
            data = yaml.safe_load(content)
            assert isinstance(data, dict)
            assert "summary" in data
            assert "tool_calls" in data
            assert data["summary"]["total"] > 0
        except ImportError:
            pass

    def test_registry_has_header(self, tmp_path):
        """Header includes the workflow instructions."""
        result = _scan_and_build(LANGGRAPH)
        out = tmp_path / "toolcalls.yaml"
        content = generate(result, output_path=out, scanned_path=".")

        assert "# toolcalls.yaml" in content
        assert "# checked:ok" in content
        assert "--fail-on-unchecked" in content
        assert "Commit this file" in content


# ---------------------------------------------------------------------------
# 2. Effect ordering within NO CHECKS
# ---------------------------------------------------------------------------


class TestRegistryEffectOrdering:
    def test_registry_effect_ordering(self, tmp_path):
        """In NO CHECKS, payment/delete before llm_call before http_write."""
        result = _scan_and_build(LANGGRAPH)
        out = tmp_path / "toolcalls.yaml"
        content = generate(result, output_path=out, scanned_path=str(LANGGRAPH))

        lines = content.splitlines()
        # Find positions of NO CHECKS group comments
        no_checks_positions = []
        for i, line in enumerate(lines):
            if "NO CHECKS" in line:
                no_checks_positions.append((i, line))

        # payment/database_delete should come before other categories
        if len(no_checks_positions) >= 2:
            first_group = no_checks_positions[0][1]
            assert any(cat in first_group for cat in ("payment", "database_delete"))


# ---------------------------------------------------------------------------
# 3. Confirmed section from # checked:ok
# ---------------------------------------------------------------------------


class TestRegistryConfirmed:
    def test_registry_confirmed(self, tmp_path):
        """Function with # checked:ok → section CONFIRMED with confirmed field."""
        result = _scan_and_build(CHECKED_OK)
        out = tmp_path / "toolcalls.yaml"
        content = generate(result, output_path=out, scanned_path=str(CHECKED_OK))

        assert "CONFIRMED" in content
        assert "confirmed:" in content
        assert "validated at API layer" in content

    def test_checked_ok_and_canary_ok(self):
        """Both # checked:ok and # canary:ok are recognized as confirmed."""
        tools = scan_directory(CHECKED_OK)
        apply_verdicts(tools)
        tools_by_name = {t.name: t for t in tools}

        checked = tools_by_name.get("confirmed_with_checked_ok")
        assert checked is not None
        assert checked.ignored is True
        assert "validated at API layer" in checked.ignore_reason

        canary = tools_by_name.get("confirmed_with_canary_ok")
        assert canary is not None
        assert canary.ignored is True
        assert "reviewed by team lead" in canary.ignore_reason

        unguarded = tools_by_name.get("still_unguarded")
        assert unguarded is not None
        assert unguarded.ignored is False


# ---------------------------------------------------------------------------
# 4. --fail-on-unchecked baseline logic
# ---------------------------------------------------------------------------


class TestFailOnUnchecked:
    def test_registry_roundtrip_windows_paths_no_false_new(self, tmp_path):
        """A baseline written with backslash paths must match itself on reload (no false NEW).

        Cross-platform reproduction of the Windows --fail-on-unchecked break:
        even on Linux, feeding a Windows-style file path through
        write → load_baseline → diff_against_baseline must yield zero NEW findings.
        """
        from diplomat_agent.models import ScanResult, Tool, SideEffect
        from diplomat_agent.reporter.registry import (
            generate,
            load_baseline,
            diff_against_baseline,
        )

        win_path = r"C:\Users\dev\project\tools.py"
        tool = Tool(
            name="delete_customer",
            file=win_path,
            line=10,
            params=[],
            side_effects=[
                SideEffect(
                    category="database_delete",
                    evidence="session.delete(c)",
                    line=10,
                    file=win_path,
                )
            ],
            verdict="UNGUARDED",
        )
        result = ScanResult(tools=[tool], scenarios=[], summary={})

        baseline_path = tmp_path / "toolcalls.yaml"
        generate(result, output_path=str(baseline_path), scanned_path=r"C:\Users\dev\project")
        loaded = load_baseline(baseline_path)

        new = diff_against_baseline([tool], loaded)
        assert new == [], f"path round-trip produced false NEW findings: {new}"

    def test_fail_on_unchecked_baseline(self, tmp_path):
        """CI blocks only NEW findings absent from baseline."""
        from diplomat_agent.cli import main

        # 1. Generate baseline from langgraph fixture
        baseline = tmp_path / "toolcalls.yaml"
        exit_code = main([
            str(LANGGRAPH),
            "--format", "registry",
            "--output-registry", str(baseline),
        ])
        assert exit_code == 0
        assert baseline.exists()

        # 2. Re-scan with --fail-on-unchecked using same baseline → exit 0
        exit_code = main([
            str(LANGGRAPH),
            "--format", "registry",
            "--output-registry", str(baseline),
            "--fail-on-unchecked",
        ])
        assert exit_code == 0

    def test_fail_on_unchecked_no_baseline(self, tmp_path):
        """Without baseline, --fail-on-unchecked blocks on any unchecked tool."""
        from diplomat_agent.cli import main

        # Point to a non-existent baseline
        baseline = tmp_path / "nonexistent.yaml"
        exit_code = main([
            str(LANGGRAPH),
            "--format", "registry",
            "--output-registry", str(baseline),
            "--fail-on-unchecked",
        ])
        # langgraph has unguarded tools, so should exit 1
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 5. Baseline loader
# ---------------------------------------------------------------------------


class TestBaselineLoader:
    def test_load_baseline(self, tmp_path):
        """load_baseline extracts function/file pairs from YAML."""
        result = _scan_and_build(LANGGRAPH)
        out = tmp_path / "toolcalls.yaml"
        generate(result, output_path=out, scanned_path=str(LANGGRAPH))

        entries = load_baseline(out)
        assert len(entries) > 0
        # Each entry should have function and file keys
        for entry in entries:
            assert "function" in entry
            assert "file" in entry
