# Changelog

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
