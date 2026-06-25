# Contributing to diplomat-agent

Thanks for taking a look. This project is a Python static analyzer for AI agent
codebases. It catches tool calls with real-world side effects (payments, DB
writes, emails, file system) that have no guards (auth, validation, rate limit).

This document covers the four ways to contribute and the conventions we follow.

## Quick start

```bash
git clone https://github.com/Diplomat-ai/diplomat-agent.git
cd diplomat-agent
pip install -e .
```

See [Running the tests](#running-the-tests) below for the test command.

No required runtime dependencies — the core scanner is stdlib-only. `rich` and
`pyyaml` are optional and only used by the reporter / config loader. You do not
need to install anything else to develop or run the test suite.

## How detection works (why patterns = data matters for contributors)

The scanner walks the Python AST of each file and matches call nodes against a
list of pattern dicts in [`src/diplomat_agent/scanner/patterns.py`](src/diplomat_agent/scanner/patterns.py).
Patterns are **data, not logic** — adding a new detection means appending a dict
to a list. You do not need to understand the AST visitor to contribute a pattern.

The visitor itself, the interprocedural guard tracer, and the verdict engine are
generic. They are only as good as the patterns they consume.

## Ways to contribute

### 1. Add a detection pattern

Open `src/diplomat_agent/scanner/patterns.py`, find the relevant category, and
append a dict to `SIDE_EFFECT_PATTERNS` (or `GUARD_PATTERNS` for new guard
shapes). Each entry looks like this (real example, payments category):

```python
{
    "category": "payment",
    "risk": 3,
    "match": {
        "obj_contains": ["stripe"],
        "attr_contains": [
            "create", "capture", "refund", "charge", "transfer",
            "payout", "payment", "subscription",
        ],
    },
},
```

Match keys: `func_contains`, `attr_contains`, `obj_contains`, `sql_contains`,
`name_contains`. Risk is 1 (low) to 3 (high). The header of `patterns.py`
documents every key.

Then add a fixture exercising the new pattern under `tests/fixtures/` and a
test that asserts the scanner picks it up.

### 2. Report or fix a false positive

False positive reports are the highest-signal feedback we get. Two paths:

- **Inline escape hatch** — annotate the call site with a trailing comment
  `# checked:ok — <reason>` and the scanner will suppress the finding for that
  line. Use this when the false positive is local to your codebase.
- **Upstream fix** — open an issue with the [`false-positive`](https://github.com/Diplomat-ai/diplomat-agent/labels/false-positive)
  label. Include: the function code, the incorrect finding, and why it is wrong.
  If you have a fix, send a PR that either tightens the pattern in `patterns.py`
  or adds a guard shape in `GUARD_PATTERNS`.

### 3. Add a test fixture

Test fixtures under `tests/fixtures/` are tiny Python files exercising one
detection or one guard pattern. They double as documentation of what the
scanner does. New fixtures must come with a test in `tests/` that asserts the
expected verdict (`UNGUARDED`, `PARTIALLY_GUARDED`, `GUARDED`, `LOW_RISK`, or
`OPAQUE`).

### 4. Improve documentation

README, CHANGELOG, docstrings, the scanner explainer. Typo fixes and clarity
improvements are welcome. PRs that add examples or rework the limitations
section are especially useful.

## Running the tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

The full suite runs in a few seconds. There is no integration suite, no
external service, no Docker. CI runs the same command on Python 3.10, 3.11,
and 3.12.

## Submitting changes

1. Fork and branch from `main`.
2. Keep PRs focused — one pattern, one fixture, one fix per PR.
3. Add a test for every behavior change.
4. Run the test command from [Running the tests](#running-the-tests) locally
   and paste the output (or relevant excerpt) in the PR description.
5. Update `CHANGELOG.md` under `## [Unreleased]` if your change is user-facing.

We squash-merge into `main`. Branch protection requires the test matrix to be
green before merge.

## Questions

Open a [GitHub Discussion](https://github.com/Diplomat-ai/diplomat-agent/discussions)
or an issue with the `question` label. For security issues, see `SECURITY.md`.
