# diplomat-agent — Repo Structure (v0.2.0)

Proposed final structure with justification for each choice. Justifications reference patterns observed in the benchmark repos (openai-agents-python, LangGraph, CrewAI, agentic-radar, Invariant).

```
diplomat-agent/
├── src/
│   └── diplomat_agent/            # Underscore, not hyphen — importable Python package
│       ├── __init__.py            # __version__ only
│       ├── __main__.py            # python -m diplomat_agent entry point
│       ├── cli.py                 # argparse CLI — single entry point
│       ├── models.py              # dataclasses for ToolCall, SideEffect, Guard, Verdict
│       ├── scanner/
│       │   ├── __init__.py
│       │   ├── patterns.py        # Side-effect + guard pattern catalog (data, not logic)
│       │   ├── ast_scanner.py     # AST-based file/directory scanner
│       │   └── yaml_scanner.py    # YAML config reader for dynamic tools
│       ├── analyzer/
│       │   ├── __init__.py
│       │   ├── guards.py          # Verdict computation (UNGUARDED/PARTIAL/GUARDED/LOW_RISK)
│       │   └── scenarios.py       # Risk scenario generation
│       └── reporter/
│           ├── __init__.py
│           ├── terminal.py        # Stdout report (rich optional)
│           ├── markdown.py        # Markdown output
│           ├── json_report.py     # JSON output
│           └── registry.py        # toolcalls.yaml generator
├── tests/
│   ├── fixtures/
│   │   ├── langgraph_agent/       # Fixture: LangGraph-style agent code
│   │   ├── crewai_agent/          # Fixture: CrewAI-style agent code
│   │   └── raw_python_agent/      # Fixture: plain Python agent code
│   └── test_scanner.py            # All tests — single file until >100 tests
├── examples/
│   └── diplomat-agent.yml         # Example YAML config for dynamic tools
├── docs/
│   ├── ANALYSIS.md                # Launch analysis (this research)
│   ├── REPO_STRUCTURE.md          # This file
│   └── LAUNCH.md                  # Launch posts
├── .github/
│   └── workflows/
│       └── ci.yml                 # Pytest + lint
├── pyproject.toml                 # hatchling, zero mandatory deps
├── README.md
├── LICENSE                        # Apache-2.0
├── CHANGELOG.md
├── CONTRIBUTING.md
└── SECURITY.md
```

## Justifications

### `src/diplomat_agent/` (src layout, underscore package name)

**Pattern:** openai-agents-python uses `src/agents/`. LangGraph uses `libs/langgraph/`. agentic-radar uses flat `agentic_radar/`.
**Decision:** Keep src layout. Use `diplomat_agent` to match the published CLI and the current package name. The src layout prevents accidental imports from the project root (a real issue in pytest — observed in agentic-radar's flat layout where test imports can shadow the installed package).

### `scanner/`, `analyzer/`, `reporter/` subpackages

**Pattern:** agentic-radar uses a flat module structure. Invariant uses deeply nested packages.
**Decision:** Keep the current 3-subpackage split. It maps 1:1 to the pipeline: scan → analyze → report. Not deeper than needed. Each subpackage has 2-4 files — the right granularity. Adding `registry.py` to `reporter/` for the toolcalls.yaml output.

### `tests/` with single test file

**Pattern:** openai-agents-python splits tests by module (`tests/test_agent.py`, `tests/test_tool.py`, etc.). agentic-radar has `tests/` with per-framework files.
**Decision:** Keep single `test_scanner.py` until test count exceeds ~100. Current count is 37. Splitting too early creates navigation overhead without benefit. The fixtures/ subdirectory with per-framework agent code is well-structured.

### `docs/` directory

**Pattern:** openai-agents-python uses `docs/` for Sphinx/MkDocs. LangGraph uses `docs/` for tutorials. agentic-radar has no docs/ (README only).
**Decision:** Add `docs/` for launch-specific documents (ANALYSIS.md, LAUNCH.md). NOT for auto-generated API docs — the project is too small for that. If/when docs grow, use MkDocs (the LangGraph/CrewAI pattern).

### `examples/diplomat-agent.yml`

**Pattern:** openai-agents-python has `examples/` with runnable scripts. CrewAI has `examples/` with full project templates.
**Decision:** Keep minimal. One example config file. No runnable example scripts — the README quickstart IS the example. Adding example scripts would duplicate the README and create maintenance burden.

### `.github/workflows/ci.yml`

**Pattern:** All 5 benchmarked repos have CI. None show a CI badge in README.
**Decision:** Keep CI. Consider adding a badge — diplomat-agent should model the CI-first practice it advocates. Low priority for launch.

### Files at root: `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`

**Pattern:** openai-agents-python has AGENTS.md, CLAUDE.md at root. LangGraph has AGENTS.md. CrewAI has none of these.
**Decision:** Keep. SECURITY.md is important for a security-adjacent tool — signals that the maintainers take it seriously. CONTRIBUTING.md lowers the bar for first contributions.

## Ecarts with current structure

| Current | Proposed | Why change |
|---------|----------|-----------|
| Legacy package naming | `src/diplomat_agent/` | Package naming should match the current published product and import path. |
| No `docs/` | `docs/` | Launch documents need a home. Keeps root clean. |
| No `reporter/registry.py` | Add `reporter/registry.py` | toolcalls.yaml generation is distinct from terminal/markdown/json output. Separate module. |
| Benchmark JSONs at root (`skyvern_report.json`, etc.) | Move to `data/benchmarks/` or remove from repo | 700KB JSON files at root clutter the repo. Either move to `data/benchmarks/` (if kept for reproducibility) or add to `.gitignore` (if generated). |
| `data/` at root | Keep as-is for now | Research data. Not shipped with the package. Consider moving to a separate branch or removing after launch — it's 2MB of issue data that users don't need. |
