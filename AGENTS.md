# AGENTS.md — for AI coding assistants

## What this repo is

agent-canary is a static analysis tool that scans Python codebases for tool calls (functions that change the real world: payments, database writes, HTTP calls, emails) and checks whether safety checks exist around them.

## Architecture

- `src/agent_canary/scanner/` — AST visitor that detects effects and checks
- `src/agent_canary/scanner/patterns.py` — catalogue of all known patterns (data, not logic)
- `src/agent_canary/analyzer/` — computes verdict (UNGUARDED / PARTIALLY_GUARDED / GUARDED / LOW_RISK) and missing check hints
- `src/agent_canary/reporter/` — terminal, markdown, JSON, YAML registry outputs
- `src/agent_canary/models.py` — dataclasses: SideEffect, Guard, Tool, Scenario, ScanResult
- `src/agent_canary/cli.py` — argparse CLI entry point

## Key design decisions

- **AST, not regex.** We parse Python source with the stdlib `ast` module. Regex would miss nested calls and produce false positives on strings/comments.
- **stdlib only.** Zero required dependencies. `rich` is optional for terminal color, `pyyaml` for YAML output.
- **No inter-procedural analysis.** Each function is analyzed in isolation. This limits depth but keeps the scanner fast and predictable.
- **Effects and checks, not risk scores.** The scanner reports what it sees. It does not assign severity or suggest fixes.

## Running tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

201 tests. All must pass before merge.

## Conventions

- Python 3.10+
- `from __future__ import annotations` in all source files
- No external dependencies in core scanner
- Patterns are data in `patterns.py`, not logic scattered across the codebase
