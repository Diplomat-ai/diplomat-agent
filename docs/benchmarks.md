# Benchmark Results

> Back to [README](../README.md)

## What we found scanning 16 open-source agent codebases

We ran diplomat-agent on 16 popular open-source AI agent projects — frameworks, toolkits, and reference applications that teams fork and deploy.

| Category | Unguarded instances |
|---|---|
| Database writes | 3,260 |
| Database deletes | 1,305 |
| HTTP writes (POST/PUT/PATCH) | 968 |
| Subprocess / exec / eval | 697 |
| LLM calls | 464 |
| Emails | 250 |

**76% of tool calls had zero checks at the source.**

Known false positive rate: ~5% overall, higher on payment-related patterns (~22%). Full transparency on what we got right, what we got wrong, and what we can't see → [REALITY_CHECK_RESULTS.md](../REALITY_CHECK_RESULTS.md)

These are the codebases that teams clone, adapt, and ship. The guardrails aren't missing by accident — they're expected to be added by each team, manually, with no standard and no verification that it happened.

diplomat-agent answers a question nobody could answer before: **did your team actually add the checks?**

Each unguarded tool call is a side effect that can reach production if it's not addressed during the build — a database delete with no confirmation, an HTTP call with no rate limit, a subprocess with no input validation. Not bugs today. Risks tomorrow, when an agent calls them autonomously.

One example: [Khoj](https://github.com/khoj-ai/khoj)'s `ai_update_memories` lets an LLM delete user memories with no human confirmation. Not a bug in the framework. Just a tool call that exists without a guard — like thousands of others across these codebases.

diplomat-agent reduces the attack surface — when prompt injection happens, the unguarded tool calls are the ones that get exploited. Knowing which ones have no checks is the first step.

Full breakdown by repo, including what we got wrong and what the scanner can't see → [REALITY_CHECK_RESULTS.md](../REALITY_CHECK_RESULTS.md)

## Per-repo benchmarks

| Repo | Type | Tool calls | Unguarded | CSAF findings (after dedup) | Time |
|---|---|---|---|---|---|
| Skyvern (595 files) | Application | 452 | 345 (76%) | -- | ~2s |
| Dify (1000+ files) | Platform | 1,009 | 759 (75%) | 50 (cap) | ~3s |
| PraisonAI | Framework | 1,028 | 911 (89%) | -- | ~2s |
| CrewAI | Framework | 348 | 273 (78%) | 50 (cap) | ~1s |
| Khoj | Application | 127 | 127 | 120 (4 CRITICAL, 33 HIGH) | ~1s |

These are open-source codebases, not production deployments. The numbers reflect what's in the source — not what teams may have added in their private forks. Full methodology, known false positives, and blind spots → [REALITY_CHECK_RESULTS.md](../REALITY_CHECK_RESULTS.md)
