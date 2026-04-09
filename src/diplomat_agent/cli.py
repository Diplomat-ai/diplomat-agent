"""CLI entry point for diplomat-agent.

Parses arguments and routes to the appropriate scan mode.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from diplomat_agent import __version__
from diplomat_agent.models import ScanResult
from diplomat_agent.analyzer.guards import apply_verdicts, build_summary
from diplomat_agent.analyzer.scenarios import generate_scenarios
from diplomat_agent.analyzer.checks import apply_missing_hints
from diplomat_agent.analyzer.owasp import apply_owasp


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="diplomat-agent",
        description=(
            "Scan your agentic codebase for tool calls with real-world side effects "
            "and no governance. No config required."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        metavar="PATH",
        help="Directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        help="Path to diplomat config (mode 2: explicit config)",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Generate config from scan results and exit",
    )
    parser.add_argument(
        "--format",
        choices=["terminal", "markdown", "json", "csaf", "sarif", "registry"],
        default="terminal",
        help="Output format (default: terminal)",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Write report to FILE instead of stdout",
    )
    parser.add_argument(
        "--output-registry",
        metavar="FILE",
        default=None,
        help="Path for toolcalls.yaml output (default: toolcalls.yaml)",
    )
    parser.add_argument(
        "--unguarded-only",
        action="store_true",
        help="Only show unguarded tools in the report",
    )
    parser.add_argument(
        "--fail-on-unguarded",
        action="store_true",
        help="Exit with code 1 if any unguarded tool is found (for CI)",
    )
    parser.add_argument(
        "--fail-on-unchecked",
        action="store_true",
        help="Exit with code 1 if any unchecked tool call is found (alias for --fail-on-unguarded)",
    )
    parser.add_argument(
        "--max-exposure",
        type=float,
        metavar="AMOUNT",
        help="Custom threshold for estimated financial exposure warning",
    )
    parser.add_argument(
        "--max-vulns",
        type=int,
        default=50,
        metavar="N",
        help="Maximum vulnerabilities in CSAF output (default: 50)",
    )
    parser.add_argument(
        "--no-rich",
        action="store_true",
        help="Disable rich terminal formatting even if rich is installed",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"diplomat-agent {__version__}",
    )
    return parser


def _run_auto_scan(path: Path) -> tuple[list, dict[str, int]]:
    """Run mode 1: AST auto-detection. Returns (tools, file_stats)."""
    from diplomat_agent.scanner.ast_scanner import scan_directory, last_scan_stats
    tools = scan_directory(path)
    return tools, dict(last_scan_stats)


def _run_yaml_scan(config_path: Path) -> list:
    """Run mode 2: YAML config."""
    from diplomat_agent.scanner.yaml_scanner import load_yaml_config
    return load_yaml_config(config_path)


def _write_output(content: str, output_path: Path | None) -> None:
    if output_path is None:
        sys.stdout.write(content)
    else:
        output_path.write_text(content, encoding="utf-8")
        print(f"Report written to: {output_path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """Main entry point. Returns exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # --- Determine scan target ---
    file_stats: dict[str, int] | None = None
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: config file not found: {config_path}", file=sys.stderr)
            return 2
        scanned_path = str(config_path)
        try:
            tools = _run_yaml_scan(config_path)
        except ImportError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        except (FileNotFoundError, ValueError) as exc:
            print(f"Error reading config: {exc}", file=sys.stderr)
            return 2
    else:
        scan_root = Path(args.path).resolve()
        if not scan_root.exists():
            print(f"Error: path not found: {scan_root}", file=sys.stderr)
            return 2
        if not scan_root.is_dir():
            print(f"Error: path is not a directory: {scan_root}", file=sys.stderr)
            return 2
        scanned_path = str(scan_root)
        tools, file_stats = _run_auto_scan(scan_root)

    # --- Apply verdicts ---
    apply_verdicts(tools)
    apply_missing_hints(tools)
    apply_owasp(tools)

    # --- Filter if --unguarded-only ---
    if args.unguarded_only:
        tools = [t for t in tools if t.verdict == "UNGUARDED"]

    # --- Build result ---
    scenarios = generate_scenarios(tools)
    summary = build_summary(tools, file_stats=file_stats)
    result = ScanResult(tools=tools, scenarios=scenarios, summary=summary)

    # --- Handle --init mode ---
    if args.init:
        from diplomat_agent.scanner.yaml_scanner import generate_yaml_config
        output_path = Path("diplomat-agent.yml")
        generate_yaml_config(tools, output_path)
        print(f"Generated config: {output_path}", file=sys.stderr)
        print(
            "Edit the file to adjust side effects and guards, then run:",
            file=sys.stderr,
        )
        print(f"  diplomat-agent --config {output_path}", file=sys.stderr)
        return 0

    # --- Produce output ---
    output_file = Path(args.output) if args.output else None

    # Terminal/markdown/json output (unless --format registry exclusively)
    if args.format != "registry":
        if args.format == "terminal":
            if output_file:
                from diplomat_agent.reporter.terminal import render_plain
                _write_output(render_plain(result, scanned_path), output_file)
            else:
                from diplomat_agent.reporter.terminal import print_report
                print_report(
                    result,
                    scanned_path,
                    use_rich=not args.no_rich,
                )

        elif args.format == "markdown":
            from diplomat_agent.reporter.markdown import render_markdown
            content = render_markdown(result, scanned_path)
            if output_file:
                _write_output(content, output_file)
            else:
                sys.stdout.write(content)

        elif args.format == "json":
            from diplomat_agent.reporter.json_report import render_json
            content = render_json(result, scanned_path)
            if output_file:
                _write_output(content, output_file)
            else:
                sys.stdout.write(content + "\n")

        elif args.format == "csaf":
            from diplomat_agent.csaf.converter import (
                generate_advisory_id,
                scan_to_csaf,
                write_advisory,
            )
            import json as _json

            repo_name = Path(scanned_path).name
            advisory_id = generate_advisory_id(1)
            csaf = scan_to_csaf(
                result,
                advisory_id,
                repo_name,
                max_vulns=args.max_vulns,
            )
            content = _json.dumps(csaf, indent=2)
            if output_file:
                write_advisory(csaf, str(output_file))
                print(f"CSAF advisory written to: {output_file}", file=sys.stderr)
            else:
                sys.stdout.write(content + "\n")

        elif args.format == "sarif":
            from diplomat_agent.reporter.sarif import render_sarif
            content = render_sarif(result, scanned_path)
            if output_file:
                _write_output(content, output_file)
            else:
                sys.stdout.write(content + "\n")

    # --- Load baseline BEFORE generating registry (which overwrites the file) ---
    fail_on = args.fail_on_unchecked or args.fail_on_unguarded
    baseline_entries: list[dict] | None = None
    if fail_on:
        baseline_path = Path(args.output_registry or "toolcalls.yaml")
        if baseline_path.exists():
            from diplomat_agent.reporter.registry import load_baseline
            baseline_entries = load_baseline(baseline_path)

    # Registry output
    if args.format == "registry" or args.output_registry:
        from diplomat_agent.reporter.registry import generate
        registry_path = args.output_registry or "toolcalls.yaml"
        generate(result, output_path=registry_path, scanned_path=scanned_path)
        print(f"\n\u2192 Tool call map written to {registry_path}", file=sys.stderr)

    # --- Exit code for CI: --fail-on-unchecked / --fail-on-unguarded ---
    if fail_on:
        unchecked = [t for t in result.tools
                     if not t.ignored and not t.guards
                     and t.verdict != "LOW_RISK"]

        if baseline_entries is not None:
            baseline_keys = {(tc.get("function", ""), tc.get("file", ""))
                             for tc in baseline_entries}
            new_unchecked = [t for t in unchecked
                             if (t.name, t.file) not in baseline_keys]

            if new_unchecked:
                print(
                    f"\n\u2717 {len(new_unchecked)} NEW tool calls with no checks "
                    f"(not in baseline {baseline_path})",
                    file=sys.stderr,
                )
                for t in new_unchecked:
                    print(f"  + {t.name}  {t.file}:{t.line}", file=sys.stderr)
                return 1
            else:
                print(
                    f"\n\u2713 No new unchecked tool calls "
                    f"({len(unchecked)} existing in baseline)",
                    file=sys.stderr,
                )
                return 0
        else:
            if unchecked:
                print(
                    f"\n\u2717 {len(unchecked)} tool calls with no checks",
                    file=sys.stderr,
                )
                return 1
            return 0

    return 0
