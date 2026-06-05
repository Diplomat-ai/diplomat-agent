# Changelog

## [0.5.0] — 2026-05-01

### Added
- **FIX A v1 — Intra-package inter-procedural tracing**: the scanner now
  follows plain-name same-package function calls (depth-2, cycle-safe) and
  propagates both side effects and guards from called helpers into their
  callers. Evidence format: `"session.delete(id)  [via _purge() @ svc.py:12]"`.
  Guard symmetry preserved: a helper that validates-then-writes causes its
  callers to inherit `PARTIALLY_GUARDED` rather than `UNGUARDED`.
  Class methods and cross-package calls are **not** resolved in v1 (FIX A v2).
- **FIX B v1 — Programmatic MCP tool registration**: `mcp.add_tool(fn)` /
  `app.add_tool(fn)` patterns are detected and the function is marked as
  `exposure="mcp_tool"` even without a decorator.
- **FIX C — psutil / os.kill destructive-process patterns**: `proc.kill()`,
  `proc.terminate()`, `proc.suspend()`, `os.kill(pid, sig)` are now detected
  as `destructive` side effects with risk-3 severity.
- **ANTI-FP observability-helper exclusion**: calls whose name contains
  log_, _log, audit_, track_, metric, trace_, telemetry, report_event, etc.
  are never followed inter-procedurally, preventing fake side-effect injection
  from fire-and-forget observability helpers.
- **Pattern dispatch index** (performance): `SIDE_EFFECT_PATTERNS` is indexed
  at import time by `attr_exact` value, reducing per-call pattern checks from
  ~61 to ~2 for non-matching attribute calls.
- **Path-key cache** (performance): `PackageIndex._path_key()` memoises
  `os.path.normcase(str(path.resolve()))` per path string, eliminating
  repeated `nt._getfinalpathname` syscalls on Windows.
- **Module-resolve cache** (performance): `PackageIndex._resolve_module()`
  memoises `(module, from_dir, level) → Path` to avoid repeated `exists()`
  filesystem checks for the same import across files.

### Changed
- **`attr_exact: ["terminate"]` precision fix**: the pre-existing
  `name_contains: ["terminate"]` pattern that caused `session.terminate_session()`
  false positives has been replaced with a targeted `attr_exact: ["terminate"]`
  pattern on psutil-like objects only.
- **Dedup key for inter-proc side effects** now uses `(file, category, line)`
  instead of `(category, line)` so that a side effect discovered both directly
  and via an inter-proc path does not suppress the cross-file copy.
- **Performance**: crewai (largest repo at 425 tools) scan time reduced from
  ~113s (pre-optimisation) to ~38s. Full 16-repo corpus reduced from ~600s
  to ~361s.

### Fixed
- **Windows short-path (`GUARNE~1`) regression**: `callee_file.relative_to(root)`
  failed when `_lookup_def` returned a short-form Windows path. Fixed by
  resolving `callee_file` and using `normcase` prefix comparison instead of
  `relative_to`.

### Baseline (16-repo corpus, v0.5.0)
- Total findings: **T=6,529** (was T=5,878 in v0.4.x, +651 new findings)
- Unguarded: **U=4,628** (was U=4,499)
- Unguarded ratio: **70.9%** (was 76.5% — lower is better: new findings are
  disproportionately guarded/partially-guarded thanks to FIX A guard propagation)

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
