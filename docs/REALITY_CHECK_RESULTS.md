# Reality Check — diplomat-agent benchmark results

> **What this document is:** raw scan results from 16 open-source AI agent codebases, with full transparency on what the scanner found, what it got wrong, and what it can't see.
>
> **What this document is not:** a claim that these projects are insecure. These are open-source codebases that teams fork and build on. The guardrails are expected to be added by each team. diplomat-agent checks whether they were.

Scanner version: **v0.5.0 (June 5, 2026)** · Python 3.9+ · zero dependencies · static + inter-procedural analysis (stdlib `ast`). See [Methodology & version history](#methodology--version-history) for v0.2.0 and v0.4.1 results.

---

## Before you read: what we got wrong

We believe in showing our work. Here's what the scanner doesn't handle well:

**Known false positives:**
- `payment` pattern matches internal business methods like `quota_charge.refund()` (Dify) and `_charge_usage()` (AutoGPT) that aren't actual payment operations. ~22% false positive rate on payment patterns via `name_contains: ["refund", "charge"]`.
- `destructive` pattern flagged `cv2.destroyAllWindows()` in PraisonAI — a GUI cleanup call, not a destructive operation.
- `publish` pattern (609 matches) captures MQTT `channel.publish()` and message queue patterns alongside actual content publishing. The word "publish" appears in many non-risky contexts.

**Known blind spots:**
- **Inter-procedural analysis (v0.5.0):** general call chains are now traced. When a tool
  delegates a side effect to a helper (function A → B → `session.delete()`), the effect is
  surfaced and attributed to the tool, with both the effect AND the helper’s guards resolved
  (same-package top-level functions, depth 2).
  Still out of scope (honest blind spots remaining in v0.5.0):
  - class methods (`self._helper()`) — planned
  - cross-package call chains
  - call depth > 2
  - dynamically-registered tools (built in loops / runtime factories)
  - side effects reached only through a typed client instance (e.g. `client.create()`)
- No import resolution for aliases: if you alias `import requests as r`, the scanner won't catch `r.post()`.

**If you find something we missed or got wrong, open an issue.** We'd rather fix it than pretend it's not there.

**On repo types:**
Not all repos in this benchmark are the same. Some are frameworks (CrewAI, PraisonAI) where the absence of guards is by design — the framework expects the developer to add them. Others are applications (Skyvern, Dify, Khoj, AutoGPT, SurfSense) where the tool calls were written by the teams who built the product. We scan both identically and let you draw your own conclusions from the "Type" column.

---

## Summary

**70.9% of tool calls with real-world side effects have no guard — 4,628 of 6,529, measured
across 16 OSS agent repos with diplomat-agent v0.5.0 (static + inter-procedural analysis).
Stable across 2 independent runs (±1 unit, non-determinism only).**

| | |
|---|---|
| Repos scanned | 16 (14 with findings; Stripe Agent Toolkit: Python SDK removed from root at HEAD) |
| Total tool calls with side effects | 6,529 |
| Unguarded (zero checks) | 4,628 — **70.9%** |
| Partially guarded | ~1,739 |
| Fully guarded or acknowledged | ~162 |

"Unguarded" means: the function has at least one side effect (DB write, HTTP call, subprocess, etc.) and **zero** detected checks (no input validation, no rate limit, no auth check, no approval gate, no retry bound).

---

## Results by repo

All results measured with diplomat-agent v0.5.0 (static + inter-procedural analysis, depth 2).
Repos cloned at HEAD June 5, 2026. Command: `PYTHONUTF8=1 diplomat-agent scan <path> --format json`

| Repo | Type | Tool calls | Unguarded | % |
|---|---|---|---|---|
| PraisonAI | Framework | 1,281 | 1,106 | 86% |
| CrewAI | Framework | 425 | 317 | 75% |
| MetaGPT | Framework | 212 | 179 | 84% |
| Skyvern | Application | 753 | 435 | 58% |
| AutoGPT | Application | 668 | 469 | 70% |
| Khoj | Application | 205 | 135 | 66% |
| SurfSense | Application | 824 | 371 | 45% |
| Browser-use | Application | 173 | 130 | 75% |
| OpenAgents | Application | 180 | 174 | 97% |
| FinRobot | Application | 83 | 64 | 77% |
| Open-SWE | Application | 47 | 44 | 94% |
| GPT-Researcher | Application | 10 | 6 | 60% |
| Dify (backend) | Platform | 1,361 | 967 | 71% |
| Composio | Platform | 38 | 29 | 76% |
| OpenAI Agents | SDK examples | 269 | 200 | 74% |
| Stripe Agent Toolkit | Benchmark | — | — | — |

**Note on Stripe Agent Toolkit:** the Python SDK was removed from the repo root; only
`benchmarks/` Python files remain. No tool calls detected. Not included in aggregate counts.

---

> Previous scan results (v0.2.0, v0.4.1) and the full version-over-version comparison
> are in [Methodology & version history](#methodology--version-history) below.

---

### By repo type

All figures v0.5.0 (inter-procedural tracing, depth 2). Weighted % = unguarded / total for
the type, not an average of per-repo percentages.

| Type | Repos | Weighted % unguarded | What this means |
|---|---|---|---|
| Framework | 3 | 84% | Expected — frameworks leave guards to the developer |
| Application | 9 | 62% | These teams built the product. The guards were theirs to add. |
| Platform | 2 | 71% | Same pattern as applications |
| SDK examples | 1 | 74% | Reference code that teams copy |
| Benchmark | 1 | — | Python SDK removed from root; not counted |

Application layer = 1,828/2,943 unguarded (62%), weighted. Frameworks sit higher by
design — guards are the implementor's responsibility — which lifts the 16-repo global to
~71%.

---

## What the scanner found, by category

**Note on overlap:** A single function with multiple side effects (e.g. a DB write + an HTTP call) appears in multiple rows. Category totals sum to more than the per-repo totals due to this overlap. The per-repo numbers in the table above are deduplicated — use those for aggregate statistics.

| Category | Unguarded instances (with overlap) | Present in X/16 repos | What it detects |
|----------|-----------------------------------|----------------------|------------------|
| Database writes | 3,260 | 15/16 | `session.commit()`, `cursor.execute("INSERT/UPDATE")`, `model.save()`, ORM `.create()` |
| Database deletes | 1,305 | 14/16 | `session.delete()`, `.remove()`, `.drop()`, `cursor.execute("DELETE")` |
| HTTP writes | 968 | 14/16 | `requests.post/put/patch()`, `httpx.post()`, `aiohttp` writes |
| Subprocess / exec | 697 | 10/16 | `subprocess.run()`, `os.system()`, `exec()`, `eval()` |
| Publish / storage | 609 | 7/16 | `s3.put_object()`, `.publish()`, `.upload()` ⚠️ high variance — see note below |
| LLM calls | 464 | 8/16 | `client.chat.completions.create()`, `anthropic.messages.create()` |
| Emails | 250 | 8/16 | `smtp.sendmail()`, `mailer.send()` |
| File deletes | 225 | 10/16 | `os.remove()`, `shutil.rmtree()`, `pathlib.unlink()` |
| Agent invocations | 206 | 8/16 | `graph.ainvoke()`, `chain.invoke()`, `agent.execute()` |
| Payments | 41 | 3/16 | `stripe.PaymentIntent.create()` ⚠️ see note below |

### ⚠️ Notes on specific categories

**Payments (41 matches):** Only `stripe-toolkit` (a Stripe benchmark repo) contains real Stripe API calls (32 matches). The other 9 matches are internal business methods like `quota_charge.refund()` (Dify) and `_charge_usage()` (AutoGPT) captured by the generic `name_contains: ["refund", "charge"]` pattern. These are **semantic false positives** — the pattern triggers on financial terminology in method names, not actual payment operations. We flag them because the scanner can't distinguish intent from naming.

**Publish (609 matches):** The word "publish" appears in many contexts — MQTT message queues (`channel.publish()`), S3 uploads (`s3.put_object()`), and content systems. Not all 609 are content publishing in the traditional sense. The scanner catches them all because any `.publish()` call could have side effects.

**Subprocess/exec (697 matches):** Includes legitimate build tooling and development scripts alongside genuinely risky `exec(user_input)` patterns. The scanner doesn't distinguish "runs a fixed build command" from "runs user-provided code." Both are flagged; the developer decides which ones matter.

---

## Interesting findings

These are real functions in real codebases, not synthetic examples.

**Khoj — `ai_update_memories`**
An LLM decides which user memories to keep and which to delete. Calls `UserMemoryAdapters.delete_memory(user, memory)` with no human confirmation gate. The agent autonomously rewrites what it "remembers" about you.

**OpenAI Agents — `pop_item`**
Calls `openai_client.conversations.items.delete()` — deletes conversation items from the OpenAI API without confirmation. Not a local database — an external API call that can't be undone.

**Skyvern — `workflow_delete`**
Calls `tool_workflow_delete(workflow_id=workflow_id, force=force)` with a `force` parameter and no approval step. The `force=True` path skips all safety checks.

**Dify — `dispatch_triggered_workflow`**
759 unguarded tool calls in the backend. The most common pattern: `session.commit()` after database writes with no validation layer between the agent's decision and the write operation.

**OpenAgents — 99% unguarded**
177 out of 178 tool calls have no checks. Primarily `redis_client.delete()` and `requests.post()` operations with no rate limiting or auth verification.

---

## How to read these numbers

**“~71% unguarded” is not a vulnerability score. It’s an inventory.**

Each unguarded tool call is a side effect that can reach production if it's not addressed during the build. A `session.delete()` with no confirmation gate. A `requests.post()` with no rate limit. A `subprocess.run()` with no input validation. None of these are bugs today — but each one becomes a risk the moment an agent calls it autonomously in production.

The ~71% tells you how much of that surface exists in the codebase before anyone decides what to do about it. Some of these tool calls will be protected by infrastructure (API gateways, IAM, network policies). Some will be protected by code in other layers that the scanner can't see (middleware, service layer validation). And some will reach production with no protection at all.

diplomat-agent doesn't decide which is which. Your team does. The scanner gives you the inventory so you can make that decision deliberately — at design time, not after an incident.

That's what `# checked:ok — protected by [where]` is for. Every tool call gets a verdict: fix it, acknowledge it, or leave it for the next person to discover in production.

---

## Reproduce these results

```bash
pip install diplomat-agent

# Clone any repo from the table and scan it
git clone https://github.com/skyvern-ai/skyvern.git
diplomat-agent ./skyvern
```

Every number in this document is reproducible. If you get different results, open an issue.

---

## Methodology & version history

The headline figure has been re-measured as the scanner’s precision improved. We publish the
full history rather than just the latest number.

| Version | Date | Total calls | Unguarded | % | What changed |
|---|---|---|---|---|---|
| v0.2.0 | Apr 2026 | 7,029 | 5,344 | 76% | Initial study. Intra-procedural only. Repos at HEAD Apr 2026. |
| v0.4.1 | Jun 4, 2026 | 5,878 | 4,499 | 76.5% | Repos re-cloned at HEAD (corpus drift). Reader-prefix FP fix (FIX 2). Inter-proc for decorators only. |
| v0.5.0 | Jun 5, 2026 | 6,529 | 4,628 | 70.9% | Inter-procedural call tracing (depth 2). 651 new findings; ~80% already guarded in helper. 129 genuinely new unguarded delegation paths. |

**Why the figure dropped from 76% to 71%:** v0.5.0 added same-package inter-procedural call
tracing. This surfaced 651 additional delegated side-effects — but 522 of those (80%) were
already guarded inside the helper function. The shallow scan was overcounting exposed surface
because it couldn’t see the guards inside the delegation chain. The 129 genuinely new
unguarded paths represent real exposure that v0.4.1 missed. The drop is a measurement
instrument improving, not the codebases improving.

**Each number is reproducible** by cloning the listed repos and running the matching scanner
version. The figure will continue to evolve as coverage deepens (class-method resolution is
planned for a future release); we treat that as a feature, not an inconsistency.

---

## What diplomat-agent doesn't detect (yet)

| Gap | Impact | Status |
|-----|--------|--------|
| Inter-procedural: class methods | `self._helper()` call chains not resolved | Planned |
| Inter-procedural: cross-package | Calls into third-party or separate packages | Not planned (by design) |
| Inter-procedural: depth > 2 | Long delegation chains (A → B → C → ...) | Not yet |
| Import aliases (`import requests as r`) | Misses aliased calls | Known limitation |
| TypeScript agents | Only Python supported | Roadmap |
| Runtime-generated tool calls | Static analysis can’t see dynamic tool registration | By design |

---

## Methodology

- **Scanner:** Python stdlib `ast` module. Zero dependencies. Parses the Abstract Syntax Tree of every `.py` file.
- **Detection:** 40+ patterns matching function calls with side effects (DB writes, HTTP calls, subprocess, payments, emails, file operations, LLM calls, agent invocations).
- **Guard detection:** Checks for input validation (Pydantic, type checks), rate limiting, authentication, approval gates, idempotency keys, retry bounds within the same function.
- **Verdict logic:** `UNGUARDED` = has side effects + zero guards. `PARTIALLY_GUARDED` = has guards but they don't cover all side effects. `GUARDED` = 2+ distinct guard types covering all effects. `LOW_RISK` = no side effects detected.
- **Scope:** Static analysis + inter-procedural tracing for same-package top-level functions
  (depth 2, cycle-safe). Class methods and cross-package call chains are analyzed
  intra-procedurally only.

**On database_write counts:** `session.commit()` is the most common pattern (present in 15/16 repos, estimated 2,000+ of the 3,260 database_write matches). The scanner flags `commit()` as unguarded when no validation exists in the same function. In practice, validation often exists in a service layer, middleware, or ORM model — which the scanner
cannot see (class methods and cross-package chains are not traced). This means the true
unguarded rate for database writes is likely lower than reported. Use `# checked:ok` to acknowledge commit() calls that are protected elsewhere.

---

*diplomat-agent is open source (Apache 2.0). The scanner finds the problem. [Diplomat](https://diplomat.run) governs it in production.*
