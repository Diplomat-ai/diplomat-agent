"""Tests for the CLI module: argument parsing, exit codes, output formats."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_canary.cli import main

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
        assert "tools" in data
        assert "summary" in data

    def test_json_contains_tool_names(self, capsys):
        main([str(FIXTURES / "crewai_agent"), "--format", "json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        tool_names = {t["name"] for t in data["tools"]}
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
        for tool in data["tools"]:
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
        assert "diplomat-canary" in captured.out
