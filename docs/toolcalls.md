# toolcalls.yaml registry

> Back to [README](../README.md)

## Badge

Add this badge to your README to show your repo has been scanned:

```markdown
[![diplomat-agent: scanned](https://img.shields.io/badge/diplomat--agent-scanned-E8724A)](https://github.com/Diplomat-ai/diplomat-agent)
```

## Usage

Generate a complete registry of every tool call in your codebase:

```bash
diplomat-agent . --format registry --output-registry toolcalls.yaml
```

Think of `toolcalls.yaml` like `requirements.txt` — but for what your agent can *do*, not what it depends on. Commit it to your repo. Diff it in PRs. When your agent gains the ability to write to a new system, the change shows up in the review.

## Format

The registry is a YAML file listing every detected tool call with:

- Function name and file location
- Side-effect category (database_write, http_write, destructive, etc.)
- Verdict (UNGUARDED, PARTIALLY_GUARDED, GUARDED, LOW_RISK)
- Any `# checked:ok` acknowledgment and its justification

## CI baseline

If `toolcalls.yaml` exists in the repo when running `diplomat-agent . --fail-on-unchecked`, it is used as baseline: only new findings block the build. This lets teams adopt diplomat-agent incrementally without blocking on existing findings.
