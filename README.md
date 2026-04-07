# diplomat-agent

[![PyPI version](https://img.shields.io/pypi/v/diplomat-agent)](https://pypi.org/project/diplomat-agent/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)](https://python.org)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green)](LICENSE)
[![diplomat-agent: scanned](https://img.shields.io/badge/diplomat--agent-scanned-E8724A)](https://github.com/Diplomat-ai/diplomat-agent)

> **76% of tool calls in open-source AI agent codebases have zero safeguards at the source.** Find yours in 60 seconds.

diplomat-agent scans your Python AI agent and reports every function that can change state in the real world — database writes, API calls, emails, payments, file deletions — and tells you which ones have no checks. Two commands. Immediate results.

## Quick start

```bash
pip install diplomat-agent
diplomat-agent .
```

Other output formats: `--format markdown`, `--format json`, `--format csaf`, `--format registry`.

Output:

```
diplomat-agent — governance scan

Scanned: ./my-agent
Tools with side effects: 12

⚠ send_report(endpoint, data)
  Rate limit:             NONE
  Retry bound:            NONE
  → Risk: agent could exhaust external API quota with 200 calls
  ⤷ no rate limit · no auth check
  Governance: ❌ UNGUARDED

⚠ delete_user_data(user_id)
  Batch protection:       NONE
  Confirmation step:      NONE
  → Risk: single prompt could trigger mass deletion
  ⤷ no confirmation step · no auth check
  Governance: ❌ UNGUARDED

────────────────────────────────────────────
RESULT: 8 with no checks · 3 with partial checks · 1 guarded (12 total)

  Fix              → add validation in code, the next scan picks it up
  Acknowledge      → add  # checked:ok  in your source code
  Protected elsewhere → add  # checked:ok — protected by [where]
  CI enforcement   → --fail-on-unchecked blocks PRs with new unreviewed tool calls
```

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

## toolcalls.yaml — the SBOM for your AI agent

Generate a complete registry of every tool call in your codebase:

```bash
diplomat-agent . --format registry --output-registry toolcalls.yaml
```

Think of `toolcalls.yaml` like `requirements.txt` — but for what your agent can *do*, not what it depends on. Commit it to your repo. Diff it in PRs. When your agent gains the ability to write to a new system, the change shows up in the review.

## Benchmarks

Tested on 16 open-source agent codebases (Skyvern, Dify, CrewAI, Khoj, PraisonAI...). 76% of tool calls had zero checks at the source. Scan time: 1-3 seconds per codebase.

Known false positive rate: ~5% overall. Full methodology, per-repo breakdown, and known blind spots -> [REALITY_CHECK_RESULTS.md](./REALITY_CHECK_RESULTS.md)

## From scanner to runtime

diplomat-agent finds the problem. **[Diplomat](https://diplomat.run)** fixes it in production — intercepting every tool call before execution with policy evaluation in <50ms and cryptographic receipts.

**[-> See Diplomat in action](https://diplomat.run)** · **[-> Book a discovery call](https://calendly.com/josselin-guarnelli)**

## Known limitations

- **Static analysis only** — no runtime or infra-level guards
- **Intra-procedural only** — use `# checked:ok` for guards in calling code
- **Python only** — TypeScript on the roadmap

## Learn more

- [CSAF 2.0 advisory generation](docs/csaf.md)
- [Benchmark results on 16 codebases](docs/benchmarks.md)
- [Acknowledging tool calls](docs/acknowledge.md)
- [Supported frameworks](docs/frameworks.md)
- [Full limitations](docs/limitations.md)
- [toolcalls.yaml registry](docs/toolcalls.md)

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

Apache 2.0
