# Reality Check — diplomat-agent benchmark results

> **What this document is:** raw scan results from 16 open-source AI agent codebases, with full transparency on what the scanner found, what it got wrong, and what it can't see.
>
> **What this document is not:** a claim that these projects are insecure. These are open-source codebases that teams fork and build on. The guardrails are expected to be added by each team. diplomat-agent checks whether they were.

Scanner version: v0.2.0 · Python 3.9+ · zero dependencies · static analysis only (stdlib `ast`)

---

## Before you read: what we got wrong

We believe in showing our work. Here's what the scanner doesn't handle well:

**Known false positives:**
- `payment` pattern matches internal business methods like `quota_charge.refund()` (Dify) and `_charge_usage()` (AutoGPT) that aren't actual payment operations. ~22% false positive rate on payment patterns via `name_contains: ["refund", "charge"]`.
- `destructive` pattern flagged `cv2.destroyAllWindows()` in PraisonAI — a GUI cleanup call, not a destructive operation.
- `publish` pattern (609 matches) captures MQTT `channel.publish()` and message queue patterns alongside actual content publishing. The word "publish" appears in many non-risky contexts.

**Known blind spots:**
- Limited inter-procedural analysis: decorators are resolved across files, but general call chains (function A calls function B which calls `session.delete()`) are still analyzed intra-procedurally.
- No import resolution for aliases: if you alias `import requests as r`, the scanner won't catch `r.post()`.

**If you find something we missed or got wrong, open an issue.** We'd rather fix it than pretend it's not there.

**On repo types:**
Not all repos in this benchmark are the same. Some are frameworks (CrewAI, PraisonAI) where the absence of guards is by design — the framework expects the developer to add them. Others are applications (Skyvern, Dify, Khoj, AutoGPT, SurfSense) where the tool calls were written by the teams who built the product. We scan both identically and let you draw your own conclusions from the "Type" column.

---

## Summary

| | |
|---|---|
| Repos scanned | 16 (14 with valid results) |
| Total tool calls with side effects | 7,029 |
| Unguarded (zero checks) | 5,344 (76%) |
| Partially guarded | ~1,200 |
| Fully guarded or acknowledged | ~485 |

"Unguarded" means: the function has at least one side effect (DB write, HTTP call, subprocess, etc.) and **zero** detected checks (no input validation, no rate limit, no auth check, no approval gate, no retry bound).

---

## Results by repo

These repos range from agent frameworks (CrewAI) to reference applications (Khoj, Dify, Skyvern). The scanner treats them identically — it maps tool calls and checks whether guards exist in the same function.

| Repo | Type | Files | Tool calls | Unguarded | % | Scan time |
|---|---|---|---|---|---|---|
| PraisonAI | Framework | ~800 | 1,028 | 911 | 89% | ~2s |
| CrewAI | Framework | ~400 | 348 | 273 | 78% | ~1s |
| Skyvern | Application | ~600 | 452 | 345 | 76% | ~2s |
| AutoGPT | Application | ~500 | 464 | 355 | 76% | ~2s |
| Dify (backend) | Platform | 1000+ | 1,009 | 759 | 75% | ~3s |
| Khoj | Application | ~300 | 181 | 125 | 69% | ~1s |
| SurfSense | Application | ~300 | 315 | 165 | 52% | ~1s |
| OpenAI Agents | SDK examples | ~100 | 93 | 78 | 84% | <1s |
| MetaGPT | Framework | ~400 | 205 | 186 | 91% | ~1s |
| Browser-use | Application | ~200 | 267 | 230 | 86% | ~1s |
| OpenAgents | Application | ~200 | 178 | 177 | 99% | ~1s |
| FinRobot | Application | ~100 | 69 | 55 | 80% | <1s |
| Open-SWE | Application | ~100 | 35 | 34 | 97% | <1s |
| GPT-Researcher | Application | ~100 | 31 | 27 | 87% | <1s |
| Composio | Platform | ~50 | 28 | 26 | 93% | <1s |
| Stripe Agent Toolkit | Benchmark | ~30 | 26 | 14 | 54% | <1s |

**Note:** AIHawk and LangChain-community were included in the scan run but produced empty results due to path errors at scan time. They are excluded from all counts.

### By repo type

| Type | Repos | Avg unguarded | What this means |
|---|---|---|---|
| Framework | 3 | 83% | Expected — frameworks leave guards to the developer |
| Application | 9 | 80% | These teams built the product. The guards were theirs to add. |
| Platform | 2 | 78% | Same pattern as applications |
| SDK examples | 1 | 84% | Reference code that teams copy |
| Benchmark | 1 | 54% | Test environment, not representative |

Frameworks at 83% unguarded is by design — that's how frameworks work. The relevant number is applications: **76% unguarded across 1,992 tool calls in 9 repos** (weighted aggregate). The per-repo average is 80%, but small repos like Open-SWE (35 calls, 97%) and OpenAgents (178 calls, 99%) pull that average up. The weighted number is more representative.

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

**"76% unguarded" is not a vulnerability score. It's an inventory.**

Each unguarded tool call is a side effect that can reach production if it's not addressed during the build. A `session.delete()` with no confirmation gate. A `requests.post()` with no rate limit. A `subprocess.run()` with no input validation. None of these are bugs today — but each one becomes a risk the moment an agent calls it autonomously in production.

The 76% tells you how much of that surface exists in the codebase before anyone decides what to do about it. Some of these tool calls will be protected by infrastructure (API gateways, IAM, network policies). Some will be protected by code in other layers that the scanner can't see (middleware, service layer validation). And some will reach production with no protection at all.

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

## What diplomat-agent doesn't detect (yet)

| Gap | Impact | Status |
|-----|--------|--------|
| Inter-procedural analysis | Support for same-package decorator resolution | Partial (decorators only) |
| Import aliases (`import requests as r`) | Misses aliased calls | Known limitation |
| TypeScript agents | Only Python supported | Roadmap |
| Runtime-generated tool calls | Static analysis can't see dynamic tool registration | By design |

---

## Methodology

- **Scanner:** Python stdlib `ast` module. Zero dependencies. Parses the Abstract Syntax Tree of every `.py` file.
- **Detection:** 40+ patterns matching function calls with side effects (DB writes, HTTP calls, subprocess, payments, emails, file operations, LLM calls, agent invocations).
- **Guard detection:** Checks for input validation (Pydantic, type checks), rate limiting, authentication, approval gates, idempotency keys, retry bounds within the same function.
- **Verdict logic:** `UNGUARDED` = has side effects + zero guards. `PARTIALLY_GUARDED` = has guards but they don't cover all side effects. `GUARDED` = 2+ distinct guard types covering all effects. `LOW_RISK` = no side effects detected.
- **Scope:** Intra-procedural only. Each function is analyzed independently.

**On database_write counts:** `session.commit()` is the most common pattern (present in 15/16 repos, estimated 2,000+ of the 3,260 database_write matches). The scanner flags `commit()` as unguarded when no validation exists in the same function. In practice, validation often exists in a service layer, middleware, or ORM model — which the scanner cannot see (intra-procedural only). This means the true unguarded rate for database writes is likely lower than reported. Use `# checked:ok` to acknowledge commit() calls that are protected elsewhere.

---

*diplomat-agent is open source (Apache 2.0). The scanner finds the problem. [Diplomat](https://diplomat.run) governs it in production.*
