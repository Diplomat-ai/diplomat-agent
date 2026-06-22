# Changelog

## [0.5.4] — 2026-06-22

### Fixed
- requires-python aligned to >=3.10, 3.9 removed from CI matrix
- __version__ now resolved via importlib.metadata
- removed "Estimated exposure" heuristic dollar amount from CLI output

## [0.5.3] — 2026-06-17

> First release published to PyPI. Cumulates all changes since 0.5.0 (the last PyPI release).

### Fixed — MCP false-negatives (dispatcher + executor indirection)
- **Dispatcher carrier check** (`treat_as_mcp_tool`): `@server.call_tool()` handlers
  dispatched by a FastMCP/low-level dispatcher were previously analyzed with
  `module_is_mcp=False`, skipping the OPAQUE floor and producing `LOW_RISK` for writes.
  Fix: dispatcher passes `treat_as_mcp_tool=True` so handlers are subject to the same
  honesty floor as direct `@mcp.tool` functions.
- **Executor callable indirection** (`asyncio.to_thread` / `run_in_executor` / `submit`):
  when a callable is passed by reference (not as a Call node), the carrier check never
  fired. Fix: `_has_unresolved_effect_carrier` now inspects the callable argument of
  known executor functions (`EXECUTOR_CALLABLE_ATTRS`, `EXECUTOR_CALLABLE_ARG_INDEX`).
  `create-container` (docker-mcp) now correctly surfaces as `OPAQUE`.

### Improved — OPAQUE precision (opaque_reason quality)
- `_collect_type_bindings` extended with literal type inference:
  `x = []` → `"list"`, `x = {}` → `"dict"`, `x = ""` → `"str"`, `x = 0` → `"int"`,
  `x = b""` → `"bytes"`, plus lowercase builtin constructors (`list()`, `dict()`, …).
- New `_body_stmts()` helper descends into always-executed `try`/`with` bodies so
  assignments like `port_mappings = []` inside a `try:` block are captured.
  Result: `create-container` `opaque_reason` now points to `asyncio.wait_for(pull_and_run())`
  instead of `port_mappings.append(mapping)`.

### Improved — Terminal OPAQUE framing
- `◐ OPAQUE` added to `_VERDICT_ICONS` and `_VERDICT_LABELS`.
- Plain and rich tool blocks: honest glose `not a risk rating — effect surface could not
  be statically resolved (review manually)` + `unresolved at: <reason>`.
- MCP summary line now includes opaque count: `N opaque (review)`.
- Rich renderer: OPAQUE displayed in blue (neutral, not alarming).

### Changed — Documentation
- `docs/landscape.md`: replaced `"MCP server scanning — On the roadmap"` with accurate
  description of what is shipped vs what is deliberately out of scope.
- `docs/limitations.md`: new `OPAQUE verdict — by design` section (external library
  callables, dispatcher indirection, MCP client proxies, `readOnlyHint` not trusted).
- `README.md`: Verdicts taxonomy table (5 verdicts + Posture column).

### Changed — Packaging / hygiene
- Corpus, results, and baseline artefacts untracked from git (kept on disk).
- `[tool.hatch.build.targets.sdist]` exclude list added as belt-and-suspenders.
- `datetime.datetime.utcnow()` → `datetime.datetime.now(datetime.timezone.utc)`
  (DeprecationWarning fix, Python 3.9+ compatible).

---

## [0.5.2] — 2026-06-12

### Added — Wrapped side-effects (étage 1 + étage 2)

- **GATE 1 — étage 1 OPAQUE honesty floor**: tools whose @mcp.tool body
  contains an unresolved effect-carrier (attribute call or unknown bare Name
  whose name does not match SIDE_EFFECT_PATTERN and is not in the benign
  allow-lists) are surfaced as `verdict="OPAQUE"` with a populated
  `opaque_reason`. Tools that previously vanished now stay visible. Benign
  filters: `BENIGN_BUILTIN_NAMES`, `BENIGN_ATTR_METHODS`, `BENIGN_RECEIVERS`.
- **GATE 2 — Dispatcher zero-branch fallback**: `@server.call_tool()`
  dispatchers with zero resolvable branches now emit one OPAQUE `Tool`
  (`exposure="mcp_internal"`, `opaque_reason` set) instead of disappearing
  after a stderr warning.
- **GATE 3 — `mcp_client` default `opaque_reason`** + JSON serialization:
  every `mcp_client` tool now carries a default `opaque_reason` if none was
  set by an earlier path; `opaque_reason` is now serialised in JSON when
  non-empty (omitted when empty for compact output).
- **GATE 4 — Curried dynamic registration**: `mcp.tool(name=...)(fn)` is
  detected as programmatic registration and `fn` is promoted to
  `exposure="mcp_tool"`. Evidence string mentions "programmatic".
- **GATE 5 — Étage 2 attribute-call interproc**: `obj.method(...)` calls
  inside @mcp.tool bodies are resolved when the receiver type is statically
  certain (`self.method` with known enclosing class, `Class.method` with
  PascalCase receiver, `var: SomeClass` annotation, or `var = SomeClass(...)`
  plain Assign in the same function). Reassigned bindings are dropped.
  Resolution uses `PackageIndex.lookup_class_method` and the refactored
  `_collect_callee_effects` back-end. Strictly additive: unresolved attribute
  calls still hit the GATE 1 OPAQUE floor.
- **GATE 6 — Narrow SDK verb breadth**: five high-signal verbs added to
  `SIDE_EFFECT_PATTERNS` via `attr_exact` only:
  `execute_query`, `execute_param_query` → `database_write`;
  `sendall`, `send_command` → `destructive`;
  `start_execution` → `destructive`.

### Fixed — Precision improvements (chore/v0.5.2-prod-ready, June 12, 2026)

- **GATE 1 precision fix**: `@mcp.tool` functions whose body only calls stdlib
  methods on annotated builtin-typed params (`str`, `dict`, `list`, `bytes`,
  `int`, `float`, `bool`, `complex`, `set`, `frozenset`, `tuple`, `bytearray`)
  are no longer classified as OPAQUE. These calls are never external side
  effects. The `type_bindings` dict (already computed for étage-2 interproc)
  is now threaded into `_has_unresolved_effect_carrier` to enable receiver-type
  filtering. Example: `def fmt(s: str, d: dict): return s.upper() + str(d.get("k"))`
  previously emitted OPAQUE (false positive); now drops (no external effect).
- **GATE 2 reassignment fix**: `_collect_type_bindings` now drops a variable's
  type binding when the same variable is reassigned to any call (not just a
  PascalCase constructor). Prevents false type resolution of `r = Reader(); r = get_writer();
  r.flush()` — `r`'s type is now correctly treated as uncertain.
- **BENIGN_ATTR_METHODS extended**: added `get`, `append`, `extend`, `pop`,
  `add`, `update`, `insert`, `remove`, `clear`, `discard` to the allow-list.
  These are in-memory mutation methods that cannot be external side effects.
  Excluded from the list: `send`, `write`, `execute*`, `run`, `post`.
- **Windows path YAML escaping**: `registry.py` now calls `_yaml_escape()` on
  `tool.file` and the `path` metadata field. Fixes `toolcalls.yaml` parse error
  on Windows paths containing backslashes (`\U`, `\D` YAML escape collision).
- **Carrier detector no longer flags wait primitives**: `asyncio.sleep` /
  `time.sleep` / `trio.sleep` are never external effects (added `sleep` to
  `BENIGN_ATTR_METHODS`). Removes the Phase-3 spot-check OPAQUE false positive
  on `await asyncio.sleep(...)` inside `@mcp.tool` bodies.
- **Terminal reporter no longer crashes on non-UTF-8 consoles** (Windows
  cp1252): stdout/stderr are reconfigured to UTF-8 with replacement at CLI
  entry. First-run `diplomat-agent scan .` from a default cmd.exe / PowerShell
  no longer raises `UnicodeEncodeError` on the `⚠` glyph.
- **Registry comparison no longer reports false NEW findings on Windows**:
  the `(function, file)` key is normalized to a canonical path form on both
  baseline and fresh sides, fixing permanent-red `--fail-on-unchecked` CI on
  Windows (regression from the v0.5.2 YAML path-escaping fix in GATE 0).

### New negative fixtures (GATE 2)

- `tests/fixtures/mcp/benign_typed_call.py` — stdlib-only tool on typed params;
  must NOT be OPAQUE.
- `tests/fixtures/mcp/untyped_wrapper.py` — untyped `driver` param; must be
  OPAQUE, never UNGUARDED.
- `tests/fixtures/mcp/reassigned_var.py` — reassigned receiver; must be OPAQUE,
  never UNGUARDED.

### Tests
461 passed, 1 skipped (+11 GATE 1/2 fixture tests, +1 cp1252 encoding test,
+1 Windows path round-trip test, +1 sleep benign test). Full suite green on
Python 3.13 (and 3.12).

### Documentation

- `docs/REALITY_CHECK_RESULTS.md`: closed v0.5.1 verification debt (GATE 0);
  added v0.5.2 section with two-number reporting (unguarded % over analyzable
  tools + opacity rate). Zero unexplained FPs confirmed on fixture corpus.

### JSON schema additions (v0.5.2, all additive)
`opaque_reason` (str, omitted when empty). No removals or renames.

### Acceptance scans
- pg-mcp-server: 20 → 31 visible tools, 4 → 18 UNGUARDED (14 previously
  unresolved findings now correctly classified by GATE 6).
- docker-mcp: 4 → 18 visible tools (14 surfaced by GATE 1 + GATE 5).
- k8s-mcp-server: 2 → 14 visible tools (12 surfaced by GATE 1 floor).
No `uncertain → UNGUARDED` escalations observed: guardrail held across all
three corpora.

---

## [0.5.1] — 2026-06-10

### Added (Gates 1-4, merged earlier as fix/mcp-fidelity-0.5.1)
- **GATE 1 (FP1)**: `SET TRANSACTION READ ONLY` / `BEGIN READ ONLY` excluded
  from SQL write patterns — read-only transaction setup is not a write.
- **GATE 2 (FN1)**: `asyncio.create_subprocess_exec` and
  `asyncio.create_subprocess_shell` detected as `destructive` side effects.
  Previously missed when called as `await asyncio.create_subprocess_exec(...)`.
- **GATE 3 — contract_violation flag**: `DECLARED_READONLY_BUT_WRITES` and
  `DECLARED_NONDESTRUCTIVE_BUT_DESTRUCTIVE`. Orthogonal to verdict. Surfaces in
  JSON, SARIF (rule DA010), and terminal. New JSON fields: `readonly_hint`,
  `destructive_hint`, `contract_violation`.
- **GATE 4 — OPAQUE verdict**: `session.call_tool()` / `client.call_tool()` in
  MCP client modules → `exposure="mcp_client"`, `verdict="OPAQUE"`. OPAQUE excluded
  from `%unguarded` denominator. New JSON summary fields: `opaque`,
  `files_unparsed_count`.

### Added (Gates 5-6)
- **GATE 5 — Dispatcher resolution**: `@server.call_tool()` dispatchers are
  resolved into one `Tool` per branch. Supports `if/elif` chains and `match/case`
  (Python 3.10+). Cross-file `Class.method` resolution via new
  `PackageIndex.lookup_class_method`. Unresolvable handlers → `verdict="OPAQUE"`,
  `opaque_reason` set (never `LOW_RISK`, never dropped). New `Tool` field:
  `opaque_reason: str`.
- **GATE 6 — mcp_internal folding**: helpers inside MCP modules tagged
  `exposure="mcp_internal"`. Terminal hides them by default; new `--verbose` CLI
  flag expands them. JSON is byte-identical. `build_summary` counts unchanged.

### JSON schema additions (v0.5.1, all additive)
`readonly_hint` (bool|null), `destructive_hint` (bool|null), `contract_violation`
(str), `opaque_reason` (str). Summary: `opaque`, `files_unparsed_count`.

### Benchmark
70.9% unguarded (16 repos, v0.5.0 baseline) is stable. Gate 2 adds ~+6 detections
on 3 locally re-measured repos (~0.09%). See `docs/REALITY_CHECK_RESULTS.md`.

---

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
