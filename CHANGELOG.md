# Changelog

## [0.4.0] — 2026-04-14

### Added
- **IDE integration** — zero-install support for 3 major AI-powered IDEs:
  - GitHub Copilot Chat: `.github/agents/diplomat-reviewer.agent.md`
  - Claude Code: `AGENTS.md` with reviewer instructions
  - Cursor: `.cursor/rules/diplomat-reviewer.mdc`
- **`scan` subcommand** — `diplomat-agent scan .` now works alongside
  the original `diplomat-agent .` syntax. All documentation uses `scan`.
- **`--file <path>`** — scan a single file instead of an entire directory.
  Returns results in < 200ms.
- **`--diff-only`** — scan only files modified since the last git commit.
  Designed for vibe coding workflows with frequent commits.
- **`--format sarif`** — SARIF 2.1.0 output with 9 stable rule IDs
  (DA001–DA009). Compatible with VS Code SARIF Viewer, GitHub Advanced
  Security (`upload-sarif` action), and any SARIF consumer.
- **Pre-commit hook** — `.pre-commit-hooks.yaml` for direct installation
  from the diplomat-agent repo.
- **`summary.mode`** — JSON output now includes `"mode": "diff-only"`
  and `files_scanned`/`files_changed` counts when `--diff-only` is used.
- **Inter-procedural decorator guard resolution** — the scanner now
  follows decorators defined in the same package to detect guards
  applied via wrappers (e.g. `@rate_limit` defined in a utils module).

### Changed
- **JSON schema rewrite (breaking)** — `--format json` output structure
  changed. Old: `{"tools": [], "scenarios": []}`. New:
  `{"version": "", "findings": [], "summary": {}, "scan_time_ms": 0}`.
  If you parse JSON output programmatically, update your code.
- **SARIF rules are now static** — all 9 rules (DA001–DA009) are always
  emitted in `driver.rules`, regardless of scan results. Previously,
  only rules matching found categories were emitted.

### Fixed
- `diplomat-agent scan .` now works (previously only `diplomat-agent .`
  was recognized, causing all documentation examples to fail).

### Migration guide (JSON schema)

If you consume `--format json` output:

| Old field | New field |
|---|---|
| `summary.total_tools` | `summary.total` |
| `tools` (array) | `findings` (array) |
| `scenarios` (array) | removed |
| — | `version` (new) |
| — | `scan_time_ms` (new) |
| — | `summary.mode` (new, only with `--diff-only`) |

Each finding object fields are unchanged: `function`, `file`, `line`,
`actions`, `checks`, `missing`, `verdict`.

## 0.3.0 — 2026-04-09

Inter-procedural analysis, standards alignment, competitive positioning.

- Inter-procedural decorator resolution within same package (#6, @sakshar2303)
- Body analysis for decorators to detect auth checks and rate limiting
- Hardened module resolution with path containment checks
- Relative import handling (`from . import ...`) in scanners
- OWASP Agentic Top 10 mapping: findings now include ASI-01 through ASI-10 codes
- SARIF 2.1.0 output format for GitHub Code Scanning (`--format sarif`)
- `toolcalls.yaml` spec v1.0 formalized with `spec_version` and `owasp` fields
- New docs: competitive landscape, behavioral BOM concept, compliance alignment, OWASP mapping, SARIF guide
- GitHub topics: added `governance`, `sbom`
- 309 tests (was 264), 0 regressions

## 0.2.0 — 2026-03-25

Scanner improvements based on reality check audit across 16 real agent repos.

- Fix duplicate guard labels in terminal output (Rate limit, Confirmation step)
- Contextual hints: `no rate limit` / `no auth check` only shown for relevant effect categories
- New patterns: CrewAI `crew.kickoff()`, AutoGen `initiate_chat()`, LangGraph `app.invoke()`
- Extended excluded directories: evaluation, samples, playground, notebooks, tutorial
- New fixtures: publish (S3/GCS), destructive (subprocess/os.system), file_delete, MongoDB
- 264 tests (was 220), 0 regressions

## 0.1.0 — 2026-03-23

Initial release.

- AST scanner detecting 11 effect categories and 7 check types in Python agents
- Terminal, Markdown, JSON, and YAML registry output formats
- `--fail-on-unchecked` CI gate (alias: `--fail-on-unguarded`) with baseline support
- `# checked:ok` inline annotation for acknowledged tool calls
- Benchmarked on Skyvern (382 findings), SurfSense (319), FinRobot (27)

> _Note: benchmark numbers reflect scanner v0.1.0 capabilities.
> Updated results with v0.2.0 scanner in REALITY_CHECK_RESULTS.md._
