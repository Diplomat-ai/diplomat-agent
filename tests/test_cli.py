"""Tests for the CLI module: argument parsing, exit codes, output formats."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_agent.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# --fail-on-unguarded exit code
# ---------------------------------------------------------------------------


class TestFailOnUnguarded:
    def test_exit_1_when_unguarded_tools_exist(self):
        exit_code = main([str(FIXTURES / "langgraph_agent"), "--fail-on-unguarded", "--format", "json"])
        assert exit_code == 1

    def test_exit_0_when_only_read_only(self, tmp_path):
        tool_file = tmp_path / "safe.py"
        tool_file.write_text(
            "import requests\n"
            "def get_info(url: str):\n"
            "    return requests.get(url).json()\n"
        )
        exit_code = main([str(tmp_path), "--fail-on-unguarded", "--format", "json"])
        assert exit_code == 0

    def test_exit_0_when_no_python_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("nothing here")
        exit_code = main([str(tmp_path), "--fail-on-unguarded", "--format", "json"])
        assert exit_code == 0


# ---------------------------------------------------------------------------
# --format json
# ---------------------------------------------------------------------------


class TestJsonFormat:
    def test_json_output_is_valid(self, capsys):
        main([str(FIXTURES / "langgraph_agent"), "--format", "json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, dict)
        assert "findings" in data
        assert "summary" in data
        assert "version" in data

    def test_json_contains_tool_names(self, capsys):
        main([str(FIXTURES / "crewai_agent"), "--format", "json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        tool_names = {t["function"] for t in data["findings"]}
        assert "create_ticket" in tool_names


# ---------------------------------------------------------------------------
# Default path and terminal format
# ---------------------------------------------------------------------------


class TestDefaultBehavior:
    def test_nonexistent_path_returns_2(self):
        exit_code = main(["/nonexistent/path/xyz123"])
        assert exit_code == 2

    def test_file_path_returns_2(self, tmp_path):
        f = tmp_path / "file.py"
        f.write_text("x = 1")
        exit_code = main([str(f)])
        assert exit_code == 2


# ---------------------------------------------------------------------------
# --unguarded-only
# ---------------------------------------------------------------------------


class TestUnguardedOnly:
    def test_filters_to_unguarded(self, capsys):
        main([str(FIXTURES / "langgraph_agent"), "--format", "json", "--unguarded-only"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        for tool in data["findings"]:
            assert tool["verdict"] == "UNGUARDED"


# ---------------------------------------------------------------------------
# --version (checked via SystemExit)
# ---------------------------------------------------------------------------


class TestVersion:
    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "diplomat-agent" in captured.out


# ---------------------------------------------------------------------------
# --format json structured schema
# ---------------------------------------------------------------------------


class TestJsonStructuredSchema:
    def test_json_has_version_field(self, capsys):
        main([str(FIXTURES / "langgraph_agent"), "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_json_has_scan_time_ms(self, capsys):
        main([str(FIXTURES / "langgraph_agent"), "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        assert "scan_time_ms" in data
        assert isinstance(data["scan_time_ms"], int)
        assert data["scan_time_ms"] >= 0

    def test_json_finding_has_all_fields(self, capsys):
        main([str(FIXTURES / "crewai_agent"), "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        for f in data["findings"]:
            for field in ("function", "file", "line", "actions", "checks", "missing", "verdict", "acknowledged"):
                assert field in f, f"Missing '{field}' in finding {f.get('function', '?')}"

    def test_json_guarded_finding_has_checks(self, capsys):
        main([str(FIXTURES / "langgraph_agent"), "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        guarded = [f for f in data["findings"] if f["verdict"] == "GUARDED"]
        for f in guarded:
            assert len(f["checks"]) > 0
            assert len(f["missing"]) == 0

    def test_json_unguarded_finding_has_missing(self, capsys):
        main([str(FIXTURES / "langgraph_agent"), "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        unguarded = [f for f in data["findings"] if f["verdict"] == "UNGUARDED"]
        for f in unguarded:
            assert len(f["checks"]) == 0

    def test_json_summary_total_matches(self, capsys):
        main([str(FIXTURES / "langgraph_agent"), "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        s = data["summary"]
        assert s["total"] == s["unguarded"] + s["partially_guarded"] + s["guarded"] + s["low_risk"]

    def test_json_no_stdout_noise(self, capsys):
        """JSON output must be pure JSON on stdout, no extra text."""
        main([str(FIXTURES / "langgraph_agent"), "--format", "json"])
        captured = capsys.readouterr()
        stripped = captured.out.strip()
        assert stripped.startswith("{")
        assert stripped.endswith("}")
        json.loads(stripped)  # must not raise


# ---------------------------------------------------------------------------
# --file single file scan
# ---------------------------------------------------------------------------


class TestFileScan:
    def test_file_scan_returns_findings(self, capsys):
        target = FIXTURES / "langgraph_agent" / "tools.py"
        main(["--file", str(target), "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        assert len(data["findings"]) > 0

    def test_file_scan_nonexistent_returns_error_json(self, capsys):
        exit_code = main(["--file", "/nonexistent/file.py", "--format", "json"])
        assert exit_code == 2
        data = json.loads(capsys.readouterr().out)
        assert "error" in data

    def test_file_scan_nonexistent_returns_2(self):
        exit_code = main(["--file", "/nonexistent/file.py"])
        assert exit_code == 2

    def test_file_scan_only_scans_one_file(self, capsys):
        target = FIXTURES / "langgraph_agent" / "tools.py"
        main(["--file", str(target), "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        files = {f["file"] for f in data["findings"]}
        assert len(files) <= 1


# ---------------------------------------------------------------------------
# --diff-only mode
# ---------------------------------------------------------------------------


class TestDiffOnly:
    def test_diff_only_no_git_fallback(self, tmp_path, capsys):
        """In a non-git directory, --diff-only should fall back to full scan."""
        tool_file = tmp_path / "agent.py"
        tool_file.write_text(
            "import stripe\n"
            "def charge(amount):\n"
            "    stripe.Charge.create(amount=amount)\n"
        )
        exit_code = main([str(tmp_path), "--diff-only", "--format", "json"])
        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert "findings" in data

    def test_diff_only_has_mode_field(self, capsys):
        """--diff-only must add summary.mode = 'diff-only'."""
        main([".", "--diff-only", "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        assert data["summary"]["mode"] == "diff-only"
        assert "files_scanned" in data["summary"]
        assert "files_changed" in data["summary"]

    def test_normal_scan_no_mode_field(self, capsys):
        """Without --diff-only, summary must NOT have a mode field."""
        main([str(FIXTURES / "langgraph_agent"), "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        assert "mode" not in data["summary"]


# ---------------------------------------------------------------------------
# scan subcommand (diplomat-agent scan <path>)
# ---------------------------------------------------------------------------


class TestScanSubcommand:
    def test_scan_subcommand_works(self, capsys):
        """diplomat-agent scan <path> must produce the same output as diplomat-agent <path>."""
        main(["scan", str(FIXTURES / "langgraph_agent"), "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        assert "findings" in data
        assert len(data["findings"]) > 0

    def test_backward_compat_no_scan(self, capsys):
        """diplomat-agent <path> (without scan) must continue to work."""
        main([str(FIXTURES / "langgraph_agent"), "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        assert "findings" in data
        assert len(data["findings"]) > 0

    def test_scan_default_path(self, capsys):
        """diplomat-agent scan (without path) must scan current directory."""
        main(["scan", "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        assert "scanned_path" in data

    def test_scan_with_diff_only(self, capsys):
        """diplomat-agent scan . --diff-only --format json must work."""
        code = main(["scan", ".", "--diff-only", "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        assert code == 0
        assert "findings" in data

    def test_scan_with_file_option(self, capsys):
        """diplomat-agent scan --file <path> must work."""
        target = FIXTURES / "langgraph_agent" / "tools.py"
        main(["scan", "--file", str(target), "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        assert len(data["findings"]) > 0

    def test_scan_and_no_scan_produce_same_findings(self, capsys):
        """Both syntaxes must produce identical findings."""
        main(["scan", str(FIXTURES / "langgraph_agent"), "--format", "json"])
        out1 = capsys.readouterr().out
        main([str(FIXTURES / "langgraph_agent"), "--format", "json"])
        out2 = capsys.readouterr().out
        d1, d2 = json.loads(out1), json.loads(out2)
        assert len(d1["findings"]) == len(d2["findings"])
        names1 = {f["function"] for f in d1["findings"]}
        names2 = {f["function"] for f in d2["findings"]}
        assert names1 == names2
