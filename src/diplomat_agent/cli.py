"""CLI entry point for diplomat-agent.

Parses arguments and routes to the appropriate scan mode.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
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
        epilog="Tip: 'diplomat-agent scan <path>' and 'diplomat-agent <path>' are equivalent.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        metavar="PATH",
        help="Directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--file",
        metavar="FILE",
        help="Scan a single Python file instead of a directory",
    )
    parser.add_argument(
        "--diff-only",
        action="store_true",
        help="Only scan files modified since the last git commit",
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
        "--mcp",
        action="store_true",
        help="Restrict report to MCP-exposed tools only (exposure != internal)",
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
        "--verbose",
        action="store_true",
        help="Show mcp_internal helpers in terminal output (hidden by default)",
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
    # Windows consoles default to cp1252; our terminal reporter emits non-ASCII glyphs (⚠, etc.).
    # Reconfigure stdout/stderr to UTF-8 with replacement so a narrow console degrades gracefully
    # instead of raising UnicodeEncodeError. No-op on already-UTF-8 streams and on non-reconfigurable
    # streams (e.g. captured pipes), guarded so it never itself raises.
    for _stream in (sys.stdout, sys.stderr):
        _reconfig = getattr(_stream, "reconfigure", None)
        if callable(_reconfig):
            try:
                _reconfig(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass

    # Support 'scan' subcommand: strip it so both syntaxes are identical.
    # diplomat-agent scan <path> → diplomat-agent <path>
    if argv is not None:
        if argv and argv[0] == "scan":
            argv = argv[1:]
    else:
        import sys as _sys
        raw = _sys.argv[1:]
        if raw and raw[0] == "scan":
            argv = raw[1:]

    parser = _build_parser()
    args = parser.parse_args(argv)

    scan_start = time.monotonic()

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
    elif args.file:
        # --file: scan a single file
        file_path = Path(args.file).resolve()
        if not file_path.exists():
            if args.format == "json":
                sys.stdout.write(json.dumps({"error": f"File not found: {args.file}"}) + "\n")
                return 2
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 2
        if not file_path.is_file():
            print(f"Error: not a file: {args.file}", file=sys.stderr)
            return 2
        scanned_path = str(file_path)
        from diplomat_agent.scanner.ast_scanner import scan_file
        _parse_errs: list[str] = []
        tools = scan_file(file_path, _parse_errors=_parse_errs)
        file_stats = {
            "files_scanned": 1,
            "files_skipped": 0,
            "files_unparsed": _parse_errs,
            "dispatcher_files": [],
        }
    elif args.diff_only:
        # --diff-only: scan only git-modified Python files
        scan_root = Path(args.path).resolve()
        scanned_path = str(scan_root)
        try:
            result = subprocess.run(  # checked:ok — internal git diff, not an agent tool call
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True, text=True,
                cwd=scan_root,
            )
            if result.returncode != 0:
                print("Warning: not a git repo or git error, falling back to full scan", file=sys.stderr)
                tools, file_stats = _run_auto_scan(scan_root)
            else:
                changed = [
                    scan_root / f.strip()
                    for f in result.stdout.splitlines()
                    if f.strip().endswith(".py")
                ]
                # Also include untracked Python files
                untracked_result = subprocess.run(  # checked:ok — internal git ls-files
                    ["git", "ls-files", "--others", "--exclude-standard"],
                    capture_output=True, text=True,
                    cwd=scan_root,
                )
                if untracked_result.returncode == 0:
                    changed.extend(
                        scan_root / f.strip()
                        for f in untracked_result.stdout.splitlines()
                        if f.strip().endswith(".py")
                    )
                from diplomat_agent.scanner.ast_scanner import scan_file
                tools = []
                files_scanned = 0
                for fp in changed:
                    if fp.exists():
                        tools.extend(scan_file(fp))
                        files_scanned += 1
                file_stats = {
                    "files_scanned": files_scanned,
                    "files_skipped": 0,
                    "mode": "diff-only",
                    "files_changed": len(changed),
                }
        except FileNotFoundError:
            print("Warning: git not found, falling back to full scan", file=sys.stderr)
            tools, file_stats = _run_auto_scan(scan_root)
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

    scan_time_ms = int((time.monotonic() - scan_start) * 1000)

    # --- Apply verdicts ---
    apply_verdicts(tools)
    apply_missing_hints(tools)
    apply_owasp(tools)

    # --- Compute MCP summary BEFORE any filtering (always from full list) ---
    _mcp_tools = [t for t in tools if t.exposure == "mcp_tool"]
    if _mcp_tools:
        mcp_summary: dict | None = {
            "total": len(_mcp_tools),
            "unguarded": sum(1 for t in _mcp_tools if t.verdict == "UNGUARDED"),
            "partially_guarded": sum(1 for t in _mcp_tools if t.verdict == "PARTIALLY_GUARDED"),
            "guarded": sum(1 for t in _mcp_tools if t.verdict in ("GUARDED", "LOW_RISK")),
            "opaque": sum(1 for t in _mcp_tools if t.verdict == "OPAQUE"),
        }
    else:
        mcp_summary = None

    # --- Filter if --mcp ---
    if args.mcp:
        tools = [t for t in tools if t.exposure != "internal"]

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
            _verbose = getattr(args, "verbose", False)
            if output_file:
                from diplomat_agent.reporter.terminal import render_plain
                _write_output(
                    render_plain(
                        result, scanned_path, mcp_summary=mcp_summary,
                        file_stats=file_stats, verbose=_verbose,
                    ),
                    output_file,
                )
            else:
                from diplomat_agent.reporter.terminal import print_report
                print_report(
                    result,
                    scanned_path,
                    use_rich=not args.no_rich,
                    mcp_summary=mcp_summary,
                    file_stats=file_stats,
                    verbose=_verbose,
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
            content = render_json(result, scanned_path, scan_time_ms=scan_time_ms, file_stats=file_stats)
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
            from diplomat_agent.reporter.registry import diff_against_baseline
            new_unchecked = diff_against_baseline(unchecked, baseline_entries)

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
