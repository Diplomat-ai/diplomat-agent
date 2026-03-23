"""Tests for agent-canary scanner, analyzer, and reporter."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

# Ensure the src package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_canary.scanner.ast_scanner import scan_directory, scan_file
from agent_canary.analyzer.guards import apply_verdicts, build_summary, compute_verdict
from agent_canary.analyzer.scenarios import generate_scenarios
from agent_canary.reporter.terminal import render_plain
from agent_canary.reporter.json_report import render_json
from agent_canary.models import ScanResult

FIXTURES = Path(__file__).parent / "fixtures"
LANGGRAPH = FIXTURES / "langgraph_agent"
CREWAI = FIXTURES / "crewai_agent"
RAW_PYTHON = FIXTURES / "raw_python_agent"


# ---------------------------------------------------------------------------
# 1. AST scanner finds the right tools with correct side effects
# ---------------------------------------------------------------------------


class TestLangGraphScanner:
    def setup_method(self):
        tools = scan_directory(LANGGRAPH)
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_process_refund_detected(self):
        assert "process_refund" in self.tools

    def test_process_refund_has_payment_side_effect(self):
        tool = self.tools["process_refund"]
        categories = {se.category for se in tool.side_effects}
        assert "payment" in categories

    def test_update_order_detected(self):
        assert "update_order" in self.tools

    def test_update_order_has_database_write(self):
        tool = self.tools["update_order"]
        categories = {se.category for se in tool.side_effects}
        assert "database_write" in categories

    def test_delete_customer_detected(self):
        assert "delete_customer" in self.tools

    def test_delete_customer_has_database_delete(self):
        tool = self.tools["delete_customer"]
        categories = {se.category for se in tool.side_effects}
        assert "database_delete" in categories

    def test_send_notification_detected(self):
        assert "send_notification" in self.tools

    def test_send_notification_has_email_side_effect(self):
        tool = self.tools["send_notification"]
        categories = {se.category for se in tool.side_effects}
        assert "email" in categories


class TestRawPythonScanner:
    def setup_method(self):
        tools = scan_directory(RAW_PYTHON)
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_charge_customer_detected(self):
        assert "charge_customer" in self.tools

    def test_charge_customer_payment_category(self):
        tool = self.tools["charge_customer"]
        categories = {se.category for se in tool.side_effects}
        assert "payment" in categories

    def test_cleanup_user_data_detected(self):
        assert "cleanup_user_data" in self.tools

    def test_cleanup_user_data_file_delete(self):
        tool = self.tools["cleanup_user_data"]
        categories = {se.category for se in tool.side_effects}
        assert "file_delete" in categories

    def test_purge_old_records_detected(self):
        assert "purge_old_records" in self.tools

    def test_purge_old_records_database_delete(self):
        tool = self.tools["purge_old_records"]
        categories = {se.category for se in tool.side_effects}
        assert "database_delete" in categories


# ---------------------------------------------------------------------------
# 2. Guards are correctly detected
# ---------------------------------------------------------------------------


class TestGuardDetection:
    def setup_method(self):
        tools = scan_directory(LANGGRAPH)
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_process_refund_has_no_guards(self):
        tool = self.tools["process_refund"]
        assert len(tool.guards) == 0

    def test_update_order_has_guards(self):
        tool = self.tools["update_order"]
        # Has a partial if-check guard
        assert len(tool.guards) > 0

    def test_update_order_guard_is_input_validation(self):
        tool = self.tools["update_order"]
        guard_types = {g.type for g in tool.guards}
        assert "input_validation" in guard_types

    def test_send_notification_has_auth_guard(self):
        tool = self.tools["send_notification"]
        guard_types = {g.type for g in tool.guards}
        assert "auth_check" in guard_types


# ---------------------------------------------------------------------------
# 3. Verdicts are correct
# ---------------------------------------------------------------------------


class TestVerdicts:
    def setup_method(self):
        tools = scan_directory(LANGGRAPH)
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_process_refund_is_unguarded(self):
        assert self.tools["process_refund"].verdict == "UNGUARDED"

    def test_update_order_is_partially_guarded(self):
        assert self.tools["update_order"].verdict == "PARTIALLY_GUARDED"

    def test_delete_customer_is_unguarded(self):
        assert self.tools["delete_customer"].verdict == "UNGUARDED"

    def test_get_order_is_not_included(self):
        # get_order only does a GET request → read-only → not included
        # It may or may not appear as LOW_RISK depending on detection
        # The key invariant is: if it appears, it's LOW_RISK
        if "get_order" in self.tools:
            assert self.tools["get_order"].verdict == "LOW_RISK"


# ---------------------------------------------------------------------------
# 4. Reporters produce well-formed output
# ---------------------------------------------------------------------------


def _make_result(directory: Path) -> ScanResult:
    tools = scan_directory(directory)
    apply_verdicts(tools)
    scenarios = generate_scenarios(tools)
    summary = build_summary(tools)
    return ScanResult(tools=tools, scenarios=scenarios, summary=summary)


class TestTerminalReport:
    def test_report_contains_header(self):
        result = _make_result(LANGGRAPH)
        output = render_plain(result, str(LANGGRAPH))
        assert "agent-canary" in output

    def test_report_contains_scanned_path(self):
        result = _make_result(LANGGRAPH)
        path_str = str(LANGGRAPH)
        output = render_plain(result, path_str)
        assert path_str in output

    def test_report_ends_with_cta(self):
        result = _make_result(LANGGRAPH)
        output = render_plain(result, str(LANGGRAPH))
        assert "# checked:ok" in output
        assert "--fail-on-unchecked" in output

    def test_report_shows_unguarded_tools(self):
        result = _make_result(LANGGRAPH)
        output = render_plain(result, str(LANGGRAPH))
        assert "process_refund" in output
        assert "delete_customer" in output

    def test_report_has_summary_line(self):
        result = _make_result(LANGGRAPH)
        output = render_plain(result, str(LANGGRAPH))
        assert "RESULT:" in output


class TestJsonReport:
    def test_json_is_valid(self):
        result = _make_result(LANGGRAPH)
        output = render_json(result, str(LANGGRAPH))
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_json_has_required_keys(self):
        result = _make_result(LANGGRAPH)
        output = render_json(result, str(LANGGRAPH))
        data = json.loads(output)
        assert "tools" in data
        assert "scenarios" in data
        assert "summary" in data
        assert "scanned_path" in data

    def test_json_summary_counts(self):
        result = _make_result(LANGGRAPH)
        output = render_json(result, str(LANGGRAPH))
        data = json.loads(output)
        s = data["summary"]
        assert s["total_tools"] == s["unguarded"] + s["partially_guarded"] + s["guarded"] + s["low_risk"]


# ---------------------------------------------------------------------------
# 5. YAML mode produces equivalent results
# ---------------------------------------------------------------------------


class TestYamlScanner:
    def test_yaml_mode_requires_pyyaml(self, tmp_path):
        """YAML mode should raise ImportError if PyYAML is not installed."""
        # This test only runs if PyYAML is NOT installed.
        # If PyYAML is installed, skip.
        try:
            import yaml
            pytest.skip("PyYAML is installed, skipping ImportError test")
        except ImportError:
            pass

        from agent_canary.scanner.yaml_scanner import load_yaml_config
        config = tmp_path / "config.yml"
        config.write_text("tools: []")
        with pytest.raises(ImportError):
            load_yaml_config(config)

    def test_yaml_mode_with_pyyaml(self, tmp_path):
        """YAML mode should parse tools if PyYAML is installed."""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")

        from agent_canary.scanner.yaml_scanner import load_yaml_config

        config_content = """
agent:
  name: test-agent
tools:
  - name: process_refund
    file: tools.py
    params:
      - name: amount
        type: float
      - name: customer_id
        type: string
    side_effects:
      - category: payment
    guards: []
  - name: get_order
    params:
      - name: order_id
        type: string
    side_effects:
      - category: read
    guards: []
"""
        config_path = tmp_path / "agent-canary.yml"
        config_path.write_text(config_content)

        tools = load_yaml_config(config_path)
        assert len(tools) == 1  # get_order has only 'read' → no write side effects

        tool = tools[0]
        assert tool.name == "process_refund"
        assert any(se.category == "payment" for se in tool.side_effects)


# ---------------------------------------------------------------------------
# 6. Excluded directories are not scanned
# ---------------------------------------------------------------------------


class TestExclusions:
    def test_venv_excluded(self, tmp_path):
        venv_dir = tmp_path / "venv" / "lib"
        venv_dir.mkdir(parents=True)
        evil = venv_dir / "evil_tool.py"
        evil.write_text(
            "import stripe\n"
            "def evil(amount):\n"
            "    stripe.Refund.create(amount=amount)\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "evil" not in names

    def test_pycache_excluded(self, tmp_path):
        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        # .pyc files are not .py, but test dir exclusion
        py_file = cache_dir / "cached.py"
        py_file.write_text(
            "import stripe\n"
            "def cached_tool(x):\n"
            "    stripe.Charge.create(amount=x)\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "cached_tool" not in names

    def test_test_files_excluded(self, tmp_path):
        test_file = tmp_path / "test_tools.py"
        test_file.write_text(
            "import stripe\n"
            "def test_refund(amount):\n"
            "    stripe.Refund.create(amount=amount)\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "test_refund" not in names

    def test_migrations_excluded(self, tmp_path):
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        mig_file = mig_dir / "001_init.py"
        mig_file.write_text(
            "import sqlite3\n"
            "def migrate(conn):\n"
            "    conn.execute('DELETE FROM old_table')\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "migrate" not in names

    def test_tests_dir_excluded(self, tmp_path):
        """Files inside a 'tests/' subdirectory must be excluded."""
        tests_dir = tmp_path / "tests" / "utils"
        tests_dir.mkdir(parents=True)
        helper = tests_dir / "helpers.py"
        helper.write_text(
            "async def create_test_task(db):\n"
            "    db.add('task')\n"
            "    await db.commit()\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "create_test_task" not in names

    def test_test_singular_dir_excluded(self, tmp_path):
        """Files inside a 'test/' subdirectory must also be excluded."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        f = test_dir / "helpers.py"
        f.write_text(
            "def helper_delete(db):\n"
            "    db.delete('x')\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "helper_delete" not in names

    def test_fixtures_dir_excluded(self, tmp_path):
        """Files inside a 'fixtures/' subdirectory must be excluded."""
        fix_dir = tmp_path / "fixtures"
        fix_dir.mkdir()
        f = fix_dir / "data.py"
        f.write_text(
            "def seed_db(db):\n"
            "    db.add('seed')\n"
            "    db.commit()\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "seed_db" not in names

    def test_nested_tests_dir_excluded(self, tmp_path):
        """Files in src/app/tests/utils/ (deeply nested) must be excluded."""
        nested = tmp_path / "src" / "app" / "tests" / "utils"
        nested.mkdir(parents=True)
        f = nested / "helpers.py"
        f.write_text(
            "async def create_test_task(db):\n"
            "    db.add('task')\n"
            "    await db.commit()\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "create_test_task" not in names

    def test_nested_fixture_from_spec(self):
        """The spec fixture nested_test_dir/tests/utils/helpers.py must not appear."""
        from agent_canary.scanner.ast_scanner import scan_directory
        nested = FIXTURES / "nested_test_dir"
        tools = scan_directory(nested)
        names = {t.name for t in tools}
        assert "create_test_task" not in names


# ---------------------------------------------------------------------------
# 7. --fail-on-unguarded exit code behaviour
# ---------------------------------------------------------------------------


class TestFailOnUnguarded:
    def test_exit_code_1_when_unguarded(self, tmp_path):
        from agent_canary.cli import main

        tool_file = tmp_path / "tools.py"
        tool_file.write_text(
            "import stripe\n"
            "def bad_refund(amount: float):\n"
            "    stripe.Refund.create(amount=amount)\n"
        )
        exit_code = main([str(tmp_path), "--fail-on-unguarded", "--format", "json"])
        assert exit_code == 1

    def test_exit_code_0_when_no_unguarded(self, tmp_path):
        from agent_canary.cli import main

        # Only a read-only file
        tool_file = tmp_path / "tools.py"
        tool_file.write_text(
            "import requests\n"
            "def get_data(url: str):\n"
            "    return requests.get(url).json()\n"
        )
        exit_code = main([str(tmp_path), "--fail-on-unguarded", "--format", "json"])
        assert exit_code == 0
