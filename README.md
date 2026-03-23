![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue) ![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green) ![Dependencies: 0](https://img.shields.io/badge/dependencies-0-brightgreen)

# agent-canary

Your agent can send emails, delete database rows, and charge credit cards — do you know which of those calls have no validation around them?

agent-canary scans your Python codebase and maps every function that can change the real world. For each one, it tells you what safety checks exist — and what's missing.

```
$ agent-canary ./skyvern/
382 tool calls · 307 with no checks · 66 partial · 9 confirmed

⚠ terminate                 .../script_skyvern_page.py:868
  actions:
    shutil.rmtree(temp_dir)
    os.kill(pid, signal.SIGTERM)
  checks:  none

⚠ _analyze_gmail_messages   .../composio_gmail_connector.py:228
  actions:
    session.execute(insert(messages))
  checks:  none
    → no auth check · no rate limit · no idempotency key

~ session_create             .../browser.py:126
  actions:
    db.add(browser_session)
    db.commit()
  checks:
    if not current_user: raise HTTPException(403)
    → no rate limit

✓ _get_or_create_browser_state  .../script_skyvern_page.py:81  [idempotency: full]
```

## The problem

Your agent calls `stripe.Refund.create`, `session.commit`, `requests.post` — and nothing stops it from doing so twice, without auth, or with unbounded parameters. 1,075 GitHub issues across LangGraph, CrewAI, AutoGen, and OpenAI Agents SDK document tool calls executing multiple times without idempotency. 307 of 382 tool calls in Skyvern have no checks at all.

## What it does

Scans your Python source with AST analysis. No network calls. No config. No dependencies. Finds every function that triggers a real-world action (DB write, payment, email, API call, LLM invocation, file delete) and checks whether protections exist (auth, rate limit, validation, idempotency, retry bounds).

## Quickstart

```bash
pip install agent-canary
agent-canary ./my_agent/
```

Output in < 2 seconds. Zero dependencies. Try it on the included demo:

```bash
agent-canary examples/demo_agent/
```

## What gets flagged

| Tool call | Why it's flagged |
|-----------|-----------------|
| `stripe.Refund.create(amount=amount)` | No bounds on `amount`, no rate limit, no idempotency key |
| `session.commit()` in an agent tool | No auth check before the write |
| `openai.chat.completions.create()` in a retry loop | No `max_retries` or `stop_after_attempt` — unbounded LLM spend |

## CI integration

```yaml
- run: pip install agent-canary
- run: agent-canary . --fail-on-unchecked --output-registry toolcalls.yaml
```

Exit code 1 if any new tool call has no checks. Existing unguarded calls are visible but don't block CI until you address them.

## The registry

```bash
agent-canary . --format registry > toolcalls.yaml
```

Generates a YAML inventory of every tool call, its checks, and what's missing. Commit it to your repo. Diff it on PRs. Each entry can be signed off with `# checked:ok` — creating an auditable record of who reviewed what.

This is what no other tool produces: a versionable, diffable artifact that tracks your agent's entire impact surface over time. See [`examples/toolcalls.skyvern.yaml`](examples/toolcalls.skyvern.yaml) for a real excerpt.

## Benchmarked on real projects

| Project | Stars | Tool calls | Unguarded | Time |
|---------|------:|----------:|-----------:|-----:|
| [Skyvern](https://github.com/Skyvern-AI/skyvern) | 20.9k | 382 | 307 (80%) | ~2s |
| [SurfSense](https://github.com/MODSetter/SurfSense) | 13.3k | 319 | 169 (53%) | 1.4s |
| [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | 6.5k | 27 | 18 (67%) | <1s |

## How to resolve findings

| Action | How |
|--------|-----|
| **Fix** | Add validation in code. The next scan picks it up. |
| **Acknowledge** | Add `# checked:ok` as a comment on the function. |
| **Protected elsewhere** | Add `# checked:ok — protected by [middleware/gateway/etc]` |

## What it detects

**Tool calls:** `session.commit`, `db.add`, `stripe.Refund.create`, `requests.post`, `send_mail`, `openai.chat.completions.create`, `exec()`, `s3.put_object`, `os.remove`, `shutil.rmtree`

**Checks:** `Depends()` / `Security()` (FastAPI), `@login_required`, `@rate_limit`, `get_or_create`, `Field(le=, ge=)`, `max_retries=`, `confirm` / `approve` in function body

## Limitations

- **Import aliases** — `import requests as req` then `req.post()` is not detected
- **Cross-function analysis** — if the check is in the caller and the effect is in the callee, not detected
- **Python only** — TypeScript planned

## Why this exists

We analyzed 3,047 GitHub issues across LangGraph, CrewAI, AutoGen, OpenAI Agents SDK, Claude Code, and Vercel AI SDK. 737 directly document tool calls executing without checks — duplicate executions, missing rate limits, loops without bounds, payments without validation.

The most common pattern (1,075 issues): a tool call that executes multiple times when it should execute once. The cause: no idempotency, no rate limit, no circuit breaker in the code around the tool.

agent-canary doesn't fix these problems. It makes them visible.

See [methodology](docs/METHODOLOGY.md) for data sources and classification criteria.

## Configuration

For dynamic tools (MCP servers, plugins), create an `agent-canary.yml`:

```yaml
tools:
  - name: search_web
    effects: [http_write]
  - name: send_slack
    effects: [messaging]
```

## License

Apache-2.0

---

Built by the team behind Diplomat — runtime governance for AI agents.
