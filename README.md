# diplomat-agent

[![PyPI version](https://img.shields.io/pypi/v/diplomat-agent)](https://pypi.org/project/diplomat-agent/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)](https://python.org)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green)](LICENSE)
[![diplomat-agent: scanned](https://img.shields.io/badge/diplomat--agent-scanned-E8724A)](https://github.com/Diplomat-ai/diplomat-agent)

> **76% of tool calls in production AI agents have zero safeguards.** Find yours in 60 seconds.

diplomat-agent scans your Python AI agent and reports every function that can change state in the real world — database writes, API calls, emails, payments, file deletions — and tells you which ones have no checks. Two commands. Immediate results.

## Quick start

```bash
pip install diplomat-agent
diplomat-agent .
```

Output:

```
diplomat-agent — governance scan

Scanned: ./my-agent
Tool calls with side effects: 12

⚠ research_and_save(query, db_path)
  Write protection:       NONE
  Rate limit:             NONE
  → no rate limit · no auth check
  Governance: ❌ UNGUARDED

⚠ send_notification(user_id, message)
  Write protection:       NONE
  → no confirmation before send
  Governance: ❌ UNGUARDED

✓ process_order(order_id) — # checked:ok — protected by API gateway
  Governance: ✅ CONFIRMED

────────────────────────────────────────────
RESULT: 8 with no checks · 3 partial · 1 confirmed (12 total)

  Fix              → add validation in code, the next scan picks it up
  Acknowledge      → add  # checked:ok  in your source code
  Protected elsewhere → add  # checked:ok — protected by [where]
  CI enforcement   → --fail-on-unchecked blocks PRs with new unreviewed tool calls
```

## What we found scanning 16 open-source agent repos

| | Unguarded |
|---|---|
| Database writes | 3,260 |
| Database deletes | 1,305 |
| HTTP writes (POST/PUT/PATCH) | 968 |
| Subprocess / exec / eval | 697 |
| LLM calls | 464 |
| Emails | 250 |

**76% of tool calls had zero checks.**

One example: [Khoj](https://github.com/khoj-ai/khoj)'s `ai_update_memories` lets an LLM delete user memories with no human confirmation.

Full breakdown by repo → [REALITY_CHECK_RESULTS.md](./REALITY_CHECK_RESULTS.md)

## toolcalls.yaml — the SBOM for your AI agent

Generate a complete registry of every tool call in your codebase:

```bash
diplomat-agent . --format registry --output-registry toolcalls.yaml
```

Think of `toolcalls.yaml` like `requirements.txt` — but for what your agent can *do*, not what it depends on. Commit it to your repo. Diff it in PRs. When your agent gains the ability to write to a new system, the change shows up in the review.

Add this badge to your README to show your repo has been scanned:

```markdown
[![diplomat-agent: scanned](https://img.shields.io/badge/diplomat--agent-scanned-E8724A)](https://github.com/Diplomat-ai/diplomat-agent)
```

## CI integration

Add to your CI pipeline:

```yaml
- name: Diplomat governance scan
  run: |
    pip install diplomat-agent
    diplomat-agent . --fail-on-unchecked
```

`--fail-on-unchecked` blocks the PR if there are new unreviewed tool calls.

If `toolcalls.yaml` exists in the repo, it's used as baseline: only new findings block the build.

<details>
<summary><strong>What counts as a tool call</strong> (40+ patterns detected)</summary>

Any function that can change state outside the process:

- **Database writes** — `session.commit()`, `.save()`, `.create()`, `.update()`
- **Database deletes** — `session.delete()`, `.remove()`, `DELETE FROM`
- **HTTP writes** — `requests.post()`, `httpx.put()`, `client.patch()`
- **LLM calls** — `openai.chat.completions.create()`, `anthropic.messages.create()`
- **Agent invocations** — `graph.ainvoke()`, `agent.execute()`, `Runner.run_sync()`
- **Email** — `smtp.sendmail()`, `ses_client.send_email()`
- **Destructive** — `subprocess.run()`, `exec()`, `eval()`
- **Publish** — `s3.put_object()`, `client.publish()`

</details>

<details>
<summary><strong>What counts as a check</strong> (validation, rate limiting, auth, approval...)</summary>

- **Input validation** — `Field(le=10000)`, `@validator`, `if ... raise`
- **Rate limit** — `@rate_limit`, `@throttle`
- **Auth** — `Depends()`, `Security()` (FastAPI)
- **Confirmation** — `confirm`, `approve`, `review` in function body
- **Idempotency** — `idempotency_key`, `get_or_create`, `ON CONFLICT`
- **Retry bound** — `max_retries=`, `@retry(stop=stop_after_attempt())`

</details>

## Acknowledge a tool call

If a tool call is intentionally unguarded or protected elsewhere:

```python
def send_alert(message):  # checked:ok — protected by API gateway
    requests.post(ALERT_URL, json={"msg": message})
```

`# diplomat:ok`, `# checked:ok`, and `# canary:ok` all work.

## Frameworks tested

| Framework | Coverage | Unguarded % (benchmarks) |
|---|---|---|
| LangGraph | StateGraph, tool nodes, conditional edges | 76% (Skyvern) |
| CrewAI | @tool decorator, agent.execute() | 78% |
| OpenAI SDK | client.chat.completions.create(), function_call | — |
| OpenAI Agents SDK | @function_tool, Runner patterns | — |
| LangChain | @tool, BaseTool, AgentExecutor | — |
| Direct API calls | requests, httpx, aiohttp, urllib | 75% (Dify) |

## Benchmarks

| Repo | Tool calls | Unguarded | Time |
|---|---|---|---|
| Skyvern (595 files) | 452 | 345 (76%) | ~2s |
| Dify (1000+ files) | 1,009 | 759 (75%) | ~3s |
| PraisonAI | 1,028 | 911 (89%) | ~2s |
| CrewAI | 348 | 273 (78%) | ~1s |

## From scanner to runtime

diplomat-agent finds the problem. **[Diplomat](https://diplomat.run)** fixes it in production.

diplomat-agent is static analysis — it tells you which tool calls have no checks, right now, in your codebase.

[Diplomat](https://diplomat.run) is the runtime control plane — it intercepts every tool call *before execution*, evaluates it against your policies in under 50ms, and generates an immutable hash-chained receipt for every decision. Continue, review, or stop — with cryptographic proof.

The difference between knowing your agents are exposed and ensuring they can't act without authorization.

**[→ See Diplomat in action](https://diplomat.run)** · **[→ Book a discovery call](https://calendly.com/josselin-guarnelli)**

## Known limitations

- Static analysis only — cannot detect runtime-generated tool calls
- `name_contains` patterns (e.g. "refund", "charge") may match internal business methods that aren't actual payment operations (~22% FP rate on payment patterns)
- No inter-procedural analysis (doesn't follow calls across files)
- No import alias resolution

## Roadmap

- [ ] TypeScript support
- [ ] MCP server scanning
- [ ] PR comment integration
- [ ] Runtime enforcement (Diplomat runtime)

## Requirements

- Python 3.10+
- Zero dependencies (stdlib `ast` module only)
- Optional: `rich` for colored terminal output, `pyyaml` for registry

## License

Apache 2.0 — Copyright 2026 Diplomat Services SAS
