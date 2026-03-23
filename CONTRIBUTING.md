# Contributing to agent-canary

## Quick start

```bash
git clone https://github.com/Diplomat-agents/agent-canary.git
cd agent-canary
pip install -e ".[dev]"
python -m pytest tests/
```

## How to contribute

### Report a false positive

The most valuable contribution. Open an issue using the "False positive" template with the function code and the incorrect detection.

### Report a missing tool call

If agent-canary misses a function that changes the real world, open an issue with the "Missing detection" template.

### Add a pattern

Patterns are in `src/agent_canary/scanner/patterns.py`. Each pattern needs a test fixture in `tests/fixtures/` and a test in `tests/`.

## Code style

* No external dependencies in core (stdlib only)
* `rich` and `pyyaml` are optional
* Run `python -m pytest tests/` before submitting

## Pull request process

1. Fork and create a branch from `main`
2. Add tests for new patterns
3. Ensure all tests pass
4. Open a PR with a clear description
