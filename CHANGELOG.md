# Changelog

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
