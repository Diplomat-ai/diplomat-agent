# agent-canary

**What can your AI agent do to the real world?**

agent-canary finds every tool call in your Python agent that can change the real world — database writes, payments, emails, API calls, LLM invocations, dynamic code execution — and checks whether protections exist before execution.

It generates a `toolcalls.yaml` you commit to your repo: a living inventory of your agent's real-world impact surface, with the protection status of each function.

```bash
pip install agent-canary
agent-canary . --format registry
```

1.36 seconds. Zero config. Zero network calls. Everything runs locally.

## What you get

### Terminal output

```
47 tool calls · 31 with no checks · 12 partial · 4 confirmed

⚠ process_refund  agents/tools.py:42
  actions:
    stripe.Refund.create(amount=amount)
  checks:  none
    → no bounds on amount · no rate limit · no idempotency key

~ send_notification  agents/notify.py:12
  actions:
    requests.post(webhook_url, json=payload)
  checks:
    @rate_limit(max_calls=10, period=60)
    → no input validation on webhook_url

✓ update_order  agents/tools.py:67  [checked:ok — validated at API layer]
```

### toolcalls.yaml (commit this)

```yaml
summary:
  total: 47
  no_checks: 31
  partial_checks: 12
  confirmed: 4

tool_calls:

  # ⚠ NO CHECKS — payment / database_delete
  - function: process_refund
    file: agents/tools.py
    line: 42
    actions:
      - "stripe.Refund.create(amount=amount)"
    checks: []
    missing:
      - "bounds on 'amount' (numeric parameter, no limit)"
      - "rate limit"
      - "idempotency key"

  # ✓ CONFIRMED
  - function: update_order
    file: agents/tools.py
    line: 67
    actions:
      - "session.commit()"
    checks:
      - type: auth_check
        code: "Depends(get_current_user)"
    missing: []
    confirmed: "checked:ok — validated at API layer"
```

### CI integration

```yaml
# .github/workflows/agent-canary.yml
name: agent-canary
on: [pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install agent-canary
      - run: agent-canary . --fail-on-unchecked --output-registry toolcalls.yaml
```

On first run, `agent-canary . --format registry` generates the baseline `toolcalls.yaml`. Commit it. After that, `--fail-on-unchecked` only blocks new tool calls not in the baseline — existing ones are visible but don't break CI until you address them at your own pace.

## How to resolve findings

In your source code:

| Action | How |
|---|---|
| **Fix** | Add validation in code. The next scan picks it up. |
| **Acknowledge** | Add `# checked:ok` as a comment on the function. |
| **Protected elsewhere** | Add `# checked:ok — protected by [middleware/gateway/etc]` |

## What it detects

### Tool calls (actions that change the real world)

* **Database writes:** `session.add`, `session.commit`, `db.commit`, `.save()`, `.create()`, `.update()`
* **Database deletes:** `session.delete`, `os.remove`, `shutil.rmtree`
* **HTTP writes:** `requests.post/put/patch/delete`, httpx equivalents
* **Payments:** `stripe.Refund.create`, `stripe.Charge.create`, `stripe.PaymentIntent.create`
* **Email/messaging:** `send_mail`, `smtplib`, `slack_client.chat_postMessage`, twilio
* **LLM calls:** `openai.chat.completions.create`, `anthropic.messages.create`, `llm.invoke`, `ainvoke`, custom wrappers
* **Dynamic code:** `importlib.import_module`, `exec()`, `eval()`
* **Publish:** `s3.put_object`, `s3.upload_file`

### Checks (protections before execution)

* **Input validation:** `Field(le=, ge=)`, `@validator`, `if...raise ValueError`
* **Auth:** `Depends()`, `Security()` (FastAPI), `@login_required`
* **Rate limits:** `@rate_limit`, `@throttle`
* **Idempotency:** `get_or_create`, `upsert`, `ON CONFLICT`
* **Retry bounds:** `max_retries=`, `@retry(stop=stop_after_attempt())`
* **Confirmation:** `confirm`, `approve`, `review` in function body

Only `if` blocks that actually stop execution (`raise`, `return`) count as checks. A logging-only `if` is not a check.

## What it does NOT detect

Transparency on limits builds trust.

* **ORM implicit mutations** — `entity.field = x` without `session.add()`
* **Dynamic tools** — MCP servers, plugins, OpenAPI-generated tools (use `--config` YAML mode)
* **Checks in other files** — middleware, API gateways, upstream services (use `# checked:ok — protected by [where]`)
* **Cross-function analysis** — if the check is in the caller and the effect is in the callee
* **Unbounded loops** — `while True` with tool calls inside (planned)
* **TypeScript** — Python only for now (TypeScript planned)
* **Import aliases** — `import requests as req` then `req.post()`

## Benchmarked on real projects

| Project | Stars | Stack | Files | Tool calls | Time |
|---|---|---|---|---|---|
| [Skyvern](https://github.com/Skyvern-AI/skyvern) | 20.9k | Playwright + SQLAlchemy + FastAPI | 595 | 437 | ~2s |
| [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | 6.5k | AutoGen + Pandas + ReportLab | ~50 | 27 | <1s |
| [SurfSense](https://github.com/MODSetter/SurfSense) | 13.3k | LangGraph + Celery + RBAC | 395 | 319 | 1.36s |

## Why this exists

We analyzed 3,047 GitHub issues across LangGraph, CrewAI, AutoGen, OpenAI Agents SDK, Claude Code, and Vercel AI SDK. 737 directly document tool calls executing without checks — duplicate executions, missing rate limits, loops without bounds, payments without validation.

The most common pattern (1,075 issues): a tool call that executes multiple times when it should execute once. The cause: no idempotency, no rate limit, no circuit breaker in the code around the tool.

agent-canary doesn't fix these problems. It makes them visible.

## Configuration

For dynamic tools (MCP servers, plugins), create an `agent-canary.yml`:

```yaml
tools:
  - name: search_web
    effects: [http_write]
  - name: send_slack
    effects: [messaging]
```

Generate from scan: `agent-canary . --init`

## Built by

[Diplomat](https://diplomat.run) — runtime governance for AI agents.

agent-canary maps what your agents can do. Diplomat controls it at runtime.
