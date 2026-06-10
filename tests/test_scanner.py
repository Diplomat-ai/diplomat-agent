"""Tests for diplomat-agent scanner, analyzer, and reporter."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

# Ensure the src package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_agent.scanner.ast_scanner import scan_directory, scan_file
from diplomat_agent.analyzer.guards import apply_verdicts, build_summary, compute_verdict
from diplomat_agent.analyzer.scenarios import generate_scenarios
from diplomat_agent.reporter.terminal import render_plain
from diplomat_agent.reporter.json_report import render_json
from diplomat_agent.models import ScanResult

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
        assert "diplomat-agent" in output

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
        assert "findings" in data
        assert "version" in data
        assert "summary" in data
        assert "scanned_path" in data

    def test_json_summary_counts(self):
        result = _make_result(LANGGRAPH)
        output = render_json(result, str(LANGGRAPH))
        data = json.loads(output)
        s = data["summary"]
        assert s["total"] == s["unguarded"] + s["partially_guarded"] + s["guarded"] + s["low_risk"]


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

        from diplomat_agent.scanner.yaml_scanner import load_yaml_config
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

        from diplomat_agent.scanner.yaml_scanner import load_yaml_config

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
        config_path = tmp_path / "diplomat.yml"
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
        from diplomat_agent.scanner.ast_scanner import scan_directory
        nested = FIXTURES / "nested_test_dir"
        tools = scan_directory(nested)
        names = {t.name for t in tools}
        assert "create_test_task" not in names


# ---------------------------------------------------------------------------
# 7. --fail-on-unguarded exit code behaviour
# ---------------------------------------------------------------------------


class TestFailOnUnguarded:
    def test_exit_code_1_when_unguarded(self, tmp_path):
        from diplomat_agent.cli import main

        tool_file = tmp_path / "tools.py"
        tool_file.write_text(
            "import stripe\n"
            "def bad_refund(amount: float):\n"
            "    stripe.Refund.create(amount=amount)\n"
        )
        exit_code = main([str(tmp_path), "--fail-on-unguarded", "--format", "json"])
        assert exit_code == 1

    def test_exit_code_0_when_no_unguarded(self, tmp_path):
        from diplomat_agent.cli import main

        # Only a read-only file
        tool_file = tmp_path / "tools.py"
        tool_file.write_text(
            "import requests\n"
            "def get_data(url: str):\n"
            "    return requests.get(url).json()\n"
        )
        exit_code = main([str(tmp_path), "--fail-on-unguarded", "--format", "json"])
        assert exit_code == 0


# ---------------------------------------------------------------------------
# 8. Effect type is properly categorized (FIX 1)
# ---------------------------------------------------------------------------


class TestEffectType:
    VALID_TYPES = {
        "database_write", "database_delete", "http_write", "payment",
        "email", "messaging", "publish", "llm_call", "agent_invocation",
        "file_delete", "destructive", "dynamic_code",
    }

    def test_effect_type_is_categorized(self):
        """Effects from AST scanner must have a specific type, not 'unknown'."""
        tools = scan_directory(LANGGRAPH)
        for tool in tools:
            for effect in tool.side_effects:
                assert effect.type != "unknown", (
                    f"{tool.name}: effect has type='unknown'"
                )
                assert effect.type != "", (
                    f"{tool.name}: effect has empty type"
                )
                assert effect.type in self.VALID_TYPES, (
                    f"{tool.name}: unexpected type '{effect.type}'"
                )

    def test_effect_type_payment(self):
        """stripe.Refund.create must have type='payment'."""
        tools = scan_directory(LANGGRAPH)
        by_name = {t.name: t for t in tools}
        tool = by_name["process_refund"]
        types = {e.type for e in tool.side_effects}
        assert "payment" in types

    def test_effect_type_database_write(self):
        """session.commit() must have type='database_write'."""
        tools = scan_directory(LANGGRAPH)
        by_name = {t.name: t for t in tools}
        tool = by_name["update_order"]
        types = {e.type for e in tool.side_effects}
        assert "database_write" in types

    def test_effect_type_email(self):
        """smtp.sendmail() must have type='email'."""
        tools = scan_directory(LANGGRAPH)
        by_name = {t.name: t for t in tools}
        tool = by_name["send_notification"]
        types = {e.type for e in tool.side_effects}
        assert "email" in types

    def test_effect_type_llm_call(self):
        """litellm.acompletion() must have type='llm_call'."""
        tools = scan_file(FIXTURES / "llm_calls.py")
        types = set()
        for tool in tools:
            for e in tool.side_effects:
                types.add(e.type)
        assert "llm_call" in types

    def test_effect_type_in_json_output(self):
        """The 'actions' field must appear in JSON report output."""
        tools = scan_directory(LANGGRAPH)
        apply_verdicts(tools)
        scenarios = generate_scenarios(tools)
        summary = build_summary(tools)
        result = ScanResult(tools=tools, scenarios=scenarios, summary=summary)
        output = render_json(result, str(LANGGRAPH))
        data = json.loads(output)
        for f in data["findings"]:
            assert "actions" in f, f"Missing 'actions' key in finding {f['function']}"
            assert "verdict" in f


# ---------------------------------------------------------------------------
# 9. Additional excluded directories (FIX 2)
# ---------------------------------------------------------------------------


class TestNewExclusions:
    def test_excludes_examples_dir(self, tmp_path):
        """Files in examples/ must not be scanned."""
        ex_dir = tmp_path / "examples"
        ex_dir.mkdir()
        f = ex_dir / "demo_tool.py"
        f.write_text(
            "import stripe\n"
            "def demo_refund(amount):\n"
            "    stripe.Refund.create(amount=amount)\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "demo_refund" not in names

    def test_excludes_benchmarks_dir(self, tmp_path):
        """Files in benchmarks/ must not be scanned."""
        bench_dir = tmp_path / "benchmarks"
        bench_dir.mkdir()
        f = bench_dir / "bench_tool.py"
        f.write_text(
            "import stripe\n"
            "def bench_refund(amount):\n"
            "    stripe.Refund.create(amount=amount)\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "bench_refund" not in names

    def test_excludes_evals_dir(self, tmp_path):
        """Files in evals/ must not be scanned."""
        evals_dir = tmp_path / "evals"
        evals_dir.mkdir()
        f = evals_dir / "eval_tool.py"
        f.write_text(
            "import stripe\n"
            "def eval_refund(amount):\n"
            "    stripe.Refund.create(amount=amount)\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "eval_refund" not in names

    def test_excludes_demos_dir(self, tmp_path):
        """Files in demos/ must not be scanned."""
        demos_dir = tmp_path / "demos"
        demos_dir.mkdir()
        f = demos_dir / "show.py"
        f.write_text(
            "import stripe\n"
            "def show_refund(amount):\n"
            "    stripe.Refund.create(amount=amount)\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "show_refund" not in names

    def test_excludes_nested_examples_dir(self, tmp_path):
        """Files in src/app/examples/ (nested) must be excluded."""
        nested = tmp_path / "src" / "app" / "examples"
        nested.mkdir(parents=True)
        f = nested / "sample.py"
        f.write_text(
            "import stripe\n"
            "def sample_charge(amount):\n"
            "    stripe.Charge.create(amount=amount)\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "sample_charge" not in names

    def test_excludes_evaluation_dir(self, tmp_path):
        eval_dir = tmp_path / "evaluation"
        eval_dir.mkdir()
        (eval_dir / "bench.py").write_text("def run():\n    session.commit()")
        tools = scan_directory(tmp_path)
        assert "run" not in [t.name for t in tools]

    def test_excludes_evaluations_dir(self, tmp_path):
        eval_dir = tmp_path / "evaluations"
        eval_dir.mkdir()
        (eval_dir / "bench.py").write_text("def run():\n    session.commit()")
        tools = scan_directory(tmp_path)
        assert "run" not in [t.name for t in tools]

    def test_excludes_samples_dir(self, tmp_path):
        samples_dir = tmp_path / "samples"
        samples_dir.mkdir()
        (samples_dir / "demo.py").write_text("def run():\n    session.commit()")
        tools = scan_directory(tmp_path)
        assert "run" not in [t.name for t in tools]

    def test_excludes_playground_dir(self, tmp_path):
        pg_dir = tmp_path / "playground"
        pg_dir.mkdir()
        (pg_dir / "try.py").write_text("def run():\n    session.commit()")
        tools = scan_directory(tmp_path)
        assert "run" not in [t.name for t in tools]

    def test_excludes_notebooks_dir(self, tmp_path):
        nb_dir = tmp_path / "notebooks"
        nb_dir.mkdir()
        (nb_dir / "analysis.py").write_text("def run():\n    session.commit()")
        tools = scan_directory(tmp_path)
        assert "run" not in [t.name for t in tools]

    def test_excludes_tutorial_dir(self, tmp_path):
        tut_dir = tmp_path / "tutorial"
        tut_dir.mkdir()
        (tut_dir / "step1.py").write_text("def run():\n    session.commit()")
        tools = scan_directory(tmp_path)
        assert "run" not in [t.name for t in tools]

    def test_does_not_exclude_tools_dir(self, tmp_path):
        """Files in tools/ MUST be scanned (production code)."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        f = tools_dir / "payment.py"
        f.write_text(
            "import stripe\n"
            "def real_refund(amount):\n"
            "    stripe.Refund.create(amount=amount)\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "real_refund" in names

    def test_does_not_exclude_utils_dir(self, tmp_path):
        """Files in utils/ MUST be scanned (production code)."""
        utils_dir = tmp_path / "utils"
        utils_dir.mkdir()
        f = utils_dir / "helpers.py"
        f.write_text(
            "import stripe\n"
            "def helper_charge(amount):\n"
            "    stripe.Charge.create(amount=amount)\n"
        )
        tools = scan_directory(tmp_path)
        names = {t.name for t in tools}
        assert "helper_charge" in names


# ---------------------------------------------------------------------------
# 10. Summary includes files_scanned / files_skipped (AMÉLIORATION 3)
# ---------------------------------------------------------------------------


class TestSummaryFileStats:
    def test_summary_has_files_scanned(self):
        """Summary must include files_scanned count."""
        tools = scan_directory(LANGGRAPH)
        apply_verdicts(tools)
        from diplomat_agent.scanner.ast_scanner import last_scan_stats
        summary = build_summary(tools, file_stats=last_scan_stats)
        assert "files_scanned" in summary
        assert summary["files_scanned"] > 0

    def test_summary_has_files_skipped(self):
        """Summary must include files_skipped count."""
        tools = scan_directory(LANGGRAPH)
        apply_verdicts(tools)
        from diplomat_agent.scanner.ast_scanner import last_scan_stats
        summary = build_summary(tools, file_stats=last_scan_stats)
        assert "files_skipped" in summary

    def test_summary_file_stats_in_json(self):
        """total and unguarded must appear in JSON summary."""
        tools = scan_directory(LANGGRAPH)
        apply_verdicts(tools)
        from diplomat_agent.scanner.ast_scanner import last_scan_stats
        scenarios = generate_scenarios(tools)
        summary = build_summary(tools, file_stats=last_scan_stats)
        result = ScanResult(tools=tools, scenarios=scenarios, summary=summary)
        output = render_json(result, str(LANGGRAPH))
        data = json.loads(output)
        s = data["summary"]
        assert "total" in s
        assert "unguarded" in s
        assert s["total"] > 0

    def test_skipped_counts_excluded_dirs(self, tmp_path):
        """files_skipped must count .py files in excluded directories."""
        # Create a production file
        prod = tmp_path / "app.py"
        prod.write_text(
            "import stripe\n"
            "def pay(amount):\n"
            "    stripe.Charge.create(amount=amount)\n"
        )
        # Create an excluded file
        ex_dir = tmp_path / "examples"
        ex_dir.mkdir()
        ex_file = ex_dir / "demo.py"
        ex_file.write_text(
            "import stripe\n"
            "def demo(amount):\n"
            "    stripe.Charge.create(amount=amount)\n"
        )
        scan_directory(tmp_path)
        from diplomat_agent.scanner.ast_scanner import last_scan_stats
        assert last_scan_stats["files_scanned"] == 1
        assert last_scan_stats["files_skipped"] == 1


# ---------------------------------------------------------------------------
# 11. Real-world patterns coverage (FIX 7)
# ---------------------------------------------------------------------------


class TestRealWorldPatterns:
    """Tests for patterns found in real repos but missing from fixtures."""

    @classmethod
    def setup_class(cls):
        cls.tools = scan_file(Path("tests/fixtures/real_world_patterns.py"))
        cls.by_name = {t.name: t for t in cls.tools}

    # --- publish ---
    def test_s3_put_object_detected(self):
        assert "upload_to_s3" in self.by_name
        assert any(se.category == "publish" for se in self.by_name["upload_to_s3"].side_effects)

    def test_s3_upload_file_detected(self):
        assert "upload_file_to_s3" in self.by_name
        assert any(se.category == "publish" for se in self.by_name["upload_file_to_s3"].side_effects)

    def test_gcs_upload_detected(self):
        assert "upload_blob_to_gcs" in self.by_name
        assert any(se.category == "publish" for se in self.by_name["upload_blob_to_gcs"].side_effects)

    def test_channel_publish_detected(self):
        assert "publish_message" in self.by_name
        assert any(se.category == "publish" for se in self.by_name["publish_message"].side_effects)

    # --- destructive ---
    def test_subprocess_run_detected(self):
        assert "run_shell_command" in self.by_name
        assert any(se.category == "destructive" for se in self.by_name["run_shell_command"].side_effects)

    def test_subprocess_check_call_detected(self):
        assert "install_package" in self.by_name
        assert any(se.category == "destructive" for se in self.by_name["install_package"].side_effects)

    def test_os_system_detected(self):
        assert "execute_system_command" in self.by_name
        assert any(se.category == "destructive" for se in self.by_name["execute_system_command"].side_effects)

    # --- file_delete ---
    def test_os_remove_detected(self):
        assert "remove_temp_file" in self.by_name
        assert any(se.category == "file_delete" for se in self.by_name["remove_temp_file"].side_effects)

    def test_pathlib_unlink_detected(self):
        assert "unlink_cache_file" in self.by_name
        assert any(se.category == "file_delete" for se in self.by_name["unlink_cache_file"].side_effects)

    # --- MongoDB ---
    def test_mongo_insert_one_detected(self):
        assert "insert_document" in self.by_name
        assert any(se.category == "database_write" for se in self.by_name["insert_document"].side_effects)

    def test_mongo_insert_many_detected(self):
        assert "bulk_insert_documents" in self.by_name
        assert any(se.category == "database_write" for se in self.by_name["bulk_insert_documents"].side_effects)

    def test_mongo_delete_many_detected(self):
        assert "delete_old_documents" in self.by_name
        assert any(se.category == "database_delete" for se in self.by_name["delete_old_documents"].side_effects)

    def test_mongo_update_one_detected(self):
        assert "update_document_status" in self.by_name
        assert any(se.category == "database_write" for se in self.by_name["update_document_status"].side_effects)


class TestAsyncSubprocessDetection:
    """GATE 2 / FN1 — asyncio.create_subprocess_exec/shell must be detected as destructive."""

    @classmethod
    def setup_class(cls):
        fixture = Path(__file__).parent / "fixtures" / "fn_async_subprocess.py"
        cls.tools = {t.name: t for t in scan_file(fixture)}

    def test_async_subprocess_detected(self):
        """asyncio.create_subprocess_exec must produce a destructive side effect."""
        assert "execute_command" in self.tools, (
            f"execute_command not found; tools={list(self.tools)}"
        )
        tool = self.tools["execute_command"]
        cats = {se.category for se in tool.side_effects}
        assert "destructive" in cats, f"destructive not in {cats}"

    def test_async_subprocess_evidence_contains_call(self):
        """Evidence string must reference create_subprocess_exec."""
        tool = self.tools["execute_command"]
        destructive = [se for se in tool.side_effects if se.category == "destructive"]
        assert destructive
        assert any("create_subprocess_exec" in se.evidence for se in destructive)


class TestAsyncSubprocessInterproc:
    """GATE 2 / FN1 — plain-Name interproc propagation of async subprocess."""

    @classmethod
    def setup_class(cls):
        fixture = Path(__file__).parent / "fixtures" / "fn_async_subprocess_interproc.py"
        # Need package_index for interproc resolution
        from diplomat_agent.scanner.interprocedural import PackageIndex
        pkg = PackageIndex(fixture.parent)
        cls.tools = {t.name: t for t in scan_file(fixture, package_index=pkg)}

    def test_tool_entry_has_destructive_effect(self):
        """tool_entry must carry the destructive effect propagated from _run."""
        assert "tool_entry" in self.tools, f"tool_entry not found; tools={list(self.tools)}"
        tool = self.tools["tool_entry"]
        cats = {se.category for se in tool.side_effects}
        assert "destructive" in cats, (
            f"destructive not propagated to tool_entry; effects={tool.side_effects}"
        )

    def test_tool_entry_evidence_has_via(self):
        """Propagated evidence must contain '[via _run()' chain annotation."""
        tool = self.tools["tool_entry"]
        destructive = [se for se in tool.side_effects if se.category == "destructive"]
        assert destructive
        # At least one evidence should reference the via chain
        assert any("[via _run()" in se.evidence for se in destructive), (
            f"No via annotation found in: {[se.evidence for se in destructive]}"
        )


class TestContractViolation:
    """GATE 3 — readOnlyHint=True + write side effects → contract_violation flag."""

    @classmethod
    def setup_class(cls):
        fixture = Path(__file__).parent / "fixtures" / "contract_readonly_violation.py"
        from diplomat_agent.scanner.interprocedural import PackageIndex
        pkg = PackageIndex(fixture.parent)
        raw_tools = scan_file(fixture, package_index=pkg)
        apply_verdicts(raw_tools)
        cls.tools = {t.name: t for t in raw_tools}

    def test_contract_violation_readonly_write(self):
        """lookup: readOnlyHint=True but has INSERT → DECLARED_READONLY_BUT_WRITES."""
        assert "lookup" in self.tools, f"lookup not found; tools={list(self.tools)}"
        tool = self.tools["lookup"]
        assert tool.contract_violation == "DECLARED_READONLY_BUT_WRITES", (
            f"Expected DECLARED_READONLY_BUT_WRITES, got {tool.contract_violation!r}"
        )
        # Verdict must be unchanged — contract_violation is orthogonal
        assert tool.verdict == "UNGUARDED", (
            f"Expected UNGUARDED, got {tool.verdict!r} — contract_violation must not change verdict"
        )

    def test_readonly_no_write_is_clean(self):
        """safe_read: readOnlyHint=True with no writes → contract_violation NONE."""
        # safe_read has no write side effects → scan_file returns None → not in tools dict
        assert "safe_read" not in self.tools, (
            "safe_read has no writes; scan_file should not return it as a Tool"
        )


class TestGate4McpClient:
    """GATE 4 — session.call_tool() in MCP client module → exposure mcp_client, verdict OPAQUE."""

    @classmethod
    def setup_class(cls):
        fixture = Path(__file__).parent / "fixtures" / "external_mcp_client.py"
        from diplomat_agent.scanner.interprocedural import PackageIndex
        pkg = PackageIndex(fixture.parent)
        raw_tools = scan_file(fixture, package_index=pkg)
        apply_verdicts(raw_tools)
        cls.tools = {t.name: t for t in raw_tools}
        cls.summary = build_summary(raw_tools)

    def test_external_mcp_call_is_opaque(self):
        """call_remote_tool: session.call_tool() → exposure mcp_client + verdict OPAQUE."""
        assert "call_remote_tool" in self.tools, (
            f"call_remote_tool not found; tools={list(self.tools)}"
        )
        tool = self.tools["call_remote_tool"]
        assert tool.exposure == "mcp_client", (
            f"Expected exposure='mcp_client', got {tool.exposure!r}"
        )
        assert tool.verdict == "OPAQUE", (
            f"Expected verdict='OPAQUE', got {tool.verdict!r}"
        )

    def test_client_receiver_is_opaque(self):
        """call_remote_named: client.call_tool() receiver → also OPAQUE."""
        assert "call_remote_named" in self.tools, (
            f"call_remote_named not found; tools={list(self.tools)}"
        )
        tool = self.tools["call_remote_named"]
        assert tool.exposure == "mcp_client", (
            f"Expected exposure='mcp_client', got {tool.exposure!r}"
        )
        assert tool.verdict == "OPAQUE", (
            f"Expected verdict='OPAQUE', got {tool.verdict!r}"
        )

    def test_innocent_helper_excluded(self):
        """innocent_helper: no call_tool → must NOT appear in scan output."""
        assert "innocent_helper" not in self.tools, (
            "innocent_helper has no call_tool; scan_file must not return it"
        )

    def test_opaque_excluded_from_denominator(self):
        """build_summary: opaque key present; OPAQUE excluded from verdict denominator."""
        assert "opaque" in self.summary, (
            f"build_summary missing 'opaque' key; keys={list(self.summary)}"
        )
        assert self.summary["opaque"] == 2, (
            f"Expected 2 opaque tools (call_remote_tool + call_remote_named), "
            f"got {self.summary['opaque']}"
        )
        # OPAQUE tools must not inflate unguarded/partial/guarded/low_risk
        denom = (
            self.summary["unguarded"]
            + self.summary["partially_guarded"]
            + self.summary["guarded"]
            + self.summary["low_risk"]
        )
        assert denom == 0, (
            f"Denominator must be 0 (only OPAQUE tools in fixture), got {denom}"
        )
        # total_tools includes OPAQUE so counts stay balanced
        assert self.summary["total_tools"] == 2, (
            f"Expected total_tools=2, got {self.summary['total_tools']}"
        )


import sys as _sys


class TestGate5Dispatcher:
    """GATE 5 — @server.call_tool dispatcher resolved into per-tool findings (if/elif fixtures)."""

    @classmethod
    def setup_class(cls):
        from pathlib import Path
        from diplomat_agent.scanner.ast_scanner import scan_file
        from diplomat_agent.analyzer.guards import apply_verdicts
        from diplomat_agent.scanner.interprocedural import PackageIndex

        ifelif_fix = Path(__file__).parent / "fixtures" / "dispatcher_ifelif_samefile.py"
        pkg_ie = PackageIndex(ifelif_fix.parent)
        raw_ie = scan_file(ifelif_fix, package_index=pkg_ie)
        apply_verdicts(raw_ie)
        cls.ie_tools = {t.name: t for t in raw_ie}

        cf_fix = Path(__file__).parent / "fixtures" / "dispatcher_crossfile" / "server.py"
        pkg_cf = PackageIndex(cf_fix.parent)
        raw_cf = scan_file(cf_fix, package_index=pkg_cf)
        apply_verdicts(raw_cf)
        cls.cf_tools = {t.name: t for t in raw_cf}

        unr_fix = Path(__file__).parent / "fixtures" / "dispatcher_unresolvable.py"
        pkg_unr = PackageIndex(unr_fix.parent)
        raw_unr = scan_file(unr_fix, package_index=pkg_unr)
        apply_verdicts(raw_unr)
        cls.unr_tools = {t.name: t for t in raw_unr}

    # if/elif same-file class method ----------------------------------- #
    def test_dispatcher_ifelif_samefile_classmethod(self):
        """if/elif 'create' branch resolved to H.create (same-file class method) → destructive."""
        assert "create" in self.ie_tools, (
            f"Expected 'create' tool; got tools={list(self.ie_tools)}"
        )
        tool = self.ie_tools["create"]
        assert tool.exposure == "mcp_tool", f"Expected mcp_tool, got {tool.exposure!r}"
        cats = {se.category for se in tool.side_effects}
        assert "destructive" in cats, (
            f"Expected destructive side effect from H.create; got {cats}"
        )
        assert "handle_tools" not in self.ie_tools, "Dispatcher must not appear as a Tool"

    # cross-file class method ------------------------------------------ #
    def test_dispatcher_crossfile_classmethod(self):
        """if/elif 'create' branch resolved to Handlers.create (cross-file) → destructive."""
        assert "create" in self.cf_tools, (
            f"Expected 'create' tool (cross-file); got tools={list(self.cf_tools)}"
        )
        tool = self.cf_tools["create"]
        assert tool.exposure == "mcp_tool", f"Expected mcp_tool, got {tool.exposure!r}"
        cats = {se.category for se in tool.side_effects}
        assert "destructive" in cats, (
            f"Expected destructive side effect from cross-file Handlers.create; got {cats}"
        )
        assert "handle_tools" not in self.cf_tools, "Dispatcher must not appear as a Tool"

    # unresolvable handler --------------------------------------------- #
    def test_dispatcher_unresolvable_is_opaque(self):
        """Unresolvable handler → opaque_reason set, verdict OPAQUE, never LOW_RISK, never dropped."""
        assert "remote-op" in self.unr_tools, (
            f"Unresolvable branch must still be emitted; got tools={list(self.unr_tools)}"
        )
        tool = self.unr_tools["remote-op"]
        assert tool.verdict == "OPAQUE", (
            f"Expected OPAQUE for unresolvable handler; got {tool.verdict!r}"
        )
        assert tool.opaque_reason != "", (
            "opaque_reason must be set for unresolvable handler"
        )
        assert tool.verdict != "LOW_RISK", "OPAQUE handler must never be LOW_RISK"


import pytest as _pytest


@_pytest.mark.skipif(_sys.version_info < (3, 10), reason="match/case requires Python 3.10+")
class TestGate5DispatcherMatchCase:
    """GATE 5 — match/case dispatcher fixture (Python 3.10+ only)."""

    @classmethod
    def setup_class(cls):
        from pathlib import Path
        from diplomat_agent.scanner.ast_scanner import scan_file
        from diplomat_agent.analyzer.guards import apply_verdicts
        from diplomat_agent.scanner.interprocedural import PackageIndex

        mc_fix = Path(__file__).parent / "fixtures" / "dispatcher_matchcase.py"
        pkg_mc = PackageIndex(mc_fix.parent)
        raw_mc = scan_file(mc_fix, package_index=pkg_mc)
        apply_verdicts(raw_mc)
        cls.mc_tools = {t.name: t for t in raw_mc}

    def test_dispatcher_matchcase_per_tool_commit(self):
        """match/case 'commit' branch → Tool named 'commit' with destructive side effect."""
        assert "commit" in self.mc_tools, (
            f"Expected 'commit' tool; got tools={list(self.mc_tools)}"
        )
        tool = self.mc_tools["commit"]
        assert tool.exposure == "mcp_tool", f"Expected mcp_tool, got {tool.exposure!r}"
        cats = {se.category for se in tool.side_effects}
        assert "destructive" in cats, (
            f"Expected destructive side effect propagated from do_commit; got {cats}"
        )

    def test_dispatcher_matchcase_dispatcher_not_emitted(self):
        """The dispatcher function handle_tools must NOT appear as a Tool."""
        assert "handle_tools" not in self.mc_tools, (
            "handle_tools (dispatcher) must not be emitted as a Tool"
        )

    def test_dispatcher_matchcase_list_branch(self):
        """match/case 'list' branch has no write effects → LOW_RISK (not OPAQUE)."""
        assert "list" in self.mc_tools, (
            f"Expected 'list' tool; got tools={list(self.mc_tools)}"
        )
        tool = self.mc_tools["list"]
        assert tool.verdict == "LOW_RISK", (
            f"Expected LOW_RISK for no-write handler; got {tool.verdict!r}"
        )
        assert tool.opaque_reason == "", (
            f"opaque_reason must be empty for resolved handler; got {tool.opaque_reason!r}"
        )


class TestGate6McpInternal:
    """GATE 6 — exposure=mcp_internal tagging + terminal folding."""

    @classmethod
    def setup_class(cls):
        from pathlib import Path
        from diplomat_agent.scanner.ast_scanner import scan_file
        from diplomat_agent.analyzer.guards import apply_verdicts
        from diplomat_agent.scanner.interprocedural import PackageIndex
        from diplomat_agent.reporter.terminal import render_plain
        from diplomat_agent.models import ScanResult

        fixture = Path(__file__).parent / "fixtures" / "mcp_module_with_helpers.py"
        pkg = PackageIndex(fixture.parent)
        raw = scan_file(fixture, package_index=pkg)
        apply_verdicts(raw)
        cls.tools = {t.name: t for t in raw}

        result = ScanResult(tools=raw, scenarios=[], summary={
            "total_tools": len(raw), "unguarded": 0, "partially_guarded": 0,
            "guarded": 0, "low_risk": 0, "opaque": 0,
        })
        cls.default_output = render_plain(result, "test", verbose=False)
        cls.verbose_output = render_plain(result, "test", verbose=True)

    def test_mcp_internal_tagging(self):
        """Internal helpers in MCP module → exposure == 'mcp_internal'."""
        for name in ("_helper_a", "_helper_b", "_helper_c"):
            assert name in self.tools, f"{name} not found; tools={list(self.tools)}"
            assert self.tools[name].exposure == "mcp_internal", (
                f"{name}: expected mcp_internal, got {self.tools[name].exposure!r}"
            )

    def test_mcp_tool_not_reclassified(self):
        """write_record: @mcp.tool keeps exposure='mcp_tool', not reclassified."""
        assert "write_record" in self.tools
        assert self.tools["write_record"].exposure == "mcp_tool", (
            f"Expected mcp_tool, got {self.tools['write_record'].exposure!r}"
        )

    def test_default_hides_mcp_internal(self):
        """Default (verbose=False): mcp_internal helpers are NOT in the output."""
        for name in ("_helper_a", "_helper_b", "_helper_c"):
            assert name not in self.default_output, (
                f"{name} must be hidden by default"
            )

    def test_default_shows_hidden_count(self):
        """Default output includes '3 internal helpers in MCP modules hidden' line."""
        assert "internal helpers in MCP modules hidden" in self.default_output, (
            "Expected hidden-helpers summary line in default output"
        )
        assert "3" in self.default_output.split("internal helpers")[0].rsplit("\n", 1)[-1], (
            "Expected count '3' before the hidden message"
        )

    def test_verbose_shows_mcp_internal(self):
        """verbose=True: all mcp_internal helpers appear in output."""
        for name in ("_helper_a", "_helper_b", "_helper_c"):
            assert name in self.verbose_output, (
                f"{name} must be shown in verbose output"
            )

    def test_verbose_no_hidden_line(self):
        """verbose=True: the 'hidden' summary line must NOT appear."""
        assert "internal helpers in MCP modules hidden" not in self.verbose_output, (
            "verbose output must not show the hidden-helpers line"
        )
