# diplomat-agent

> v0.2.0 — 264 tests, 48+ detection patterns, 11 effect categories

Find every tool call in your AI agent that can change the real world.

`diplomat-agent` is a static scanner for Python AI agents. It maps every function that writes to a database, calls an external API, sends an email, invokes another agent, or deletes data — and tells you which ones have no checks.

## What it finds

We scanned 16 open-source agent repos. Here's what we found:

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

## What counts as a tool call

Any function that can change state outside the process:

- **Database writes** — `session.commit()`, `.save()`, `.create()`, `.update()`
- **Database deletes** — `session.delete()`, `.remove()`, `DELETE FROM`
- **HTTP writes** — `requests.post()`, `httpx.put()`, `client.patch()`
- **LLM calls** — `openai.chat.completions.create()`, `anthropic.messages.create()`
- **Agent invocations** — `graph.ainvoke()`, `agent.execute()`, `Runner.run_sync()`
- **Email** — `smtp.sendmail()`, `ses_client.send_email()`
- **Destructive** — `subprocess.run()`, `exec()`, `eval()`
- **Publish** — `s3.put_object()`, `client.publish()`

## What counts as a check

- **Input validation** — `Field(le=10000)`, `@validator`, `if ... raise`
- **Rate limit** — `@rate_limit`, `@throttle`
- **Auth** — `Depends()`, `Security()` (FastAPI)
- **Confirmation** — `confirm`, `approve`, `review` in function body
- **Idempotency** — `idempotency_key`, `get_or_create`, `ON CONFLICT`
- **Retry bound** — `max_retries=`, `@retry(stop=stop_after_attempt())`

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

### Generate the registry

```bash
diplomat-agent . --format registry --output-registry toolcalls.yaml
```

Commit `toolcalls.yaml` to your repo. Review changes in PRs. The file is a mirror of what your agent can do — it updates on every scan.

## Acknowledge a tool call

If a tool call is intentionally unguarded or protected elsewhere:

```python
def send_alert(message):  # checked:ok — protected by API gateway
    requests.post(ALERT_URL, json={"msg": message})
```

`# diplomat:ok`, `# checked:ok`, and `# canary:ok` all work.

## Frameworks tested

| Framework | Coverage |
|---|---|
| LangGraph | `graph.ainvoke()`, StateGraph patterns |
| CrewAI | `agent.execute()`, tool patterns |
| OpenAI SDK | `client.chat.completions.create()` |
| OpenAI Agents SDK | `Runner.run_sync()` |
| LangChain | `chain.invoke()`, AgentExecutor |
| Direct API calls | OpenAI, Anthropic, any HTTP client |

## Requirements

- Python 3.10+
- Zero dependencies (stdlib `ast` module only)
- Optional: `rich` for colored terminal output, `pyyaml` for registry

## Benchmarks

| Repo | Tool calls | Unguarded | Time |
|---|---|---|---|
| Skyvern (595 files) | 452 | 345 (76%) | ~2s |
| Dify (1000+ files) | 1,009 | 759 (75%) | ~3s |
| PraisonAI | 1,028 | 911 (89%) | ~2s |
| CrewAI | 348 | 273 (78%) | ~1s |

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

## License

Apache 2.0 — Copyright 2026 Diplomat Services SAS
