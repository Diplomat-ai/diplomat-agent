# Reality Check — diplomat-agent benchmark results

> **What this document is:** raw scan results from 16 open-source AI agent codebases, with full transparency on what the scanner found, what it got wrong, and what it can't see.
>
> **What this document is not:** a claim that these projects are insecure. These are open-source codebases that teams fork and build on. The guardrails are expected to be added by each team. diplomat-agent checks whether they were.

Scanner version: v0.2.0 · Python 3.10+ · zero dependencies · static analysis only (stdlib `ast`)

---

## Before you read: what we got wrong

We believe in showing our work. Here's what the scanner doesn't handle well:

**Known false positives:**
- `payment` pattern matches internal business methods like `quota_charge.refund()` (Dify) and `_charge_usage()` (AutoGPT) that aren't actual payment operations. ~22% false positive rate on payment patterns via `name_contains: ["refund", "charge"]`.
- `destructive` pattern flagged `cv2.destroyAllWindows()` in PraisonAI — a GUI cleanup call, not a destructive operation.
- `publish` pattern (609 matches) captures MQTT `channel.publish()` and message queue patterns alongside actual content publishing. The word "publish" appears in many non-risky contexts.

**Known blind spots:**
- OpenAI Agents SDK `Runner.run_sync()` is not detected — `Runner` (capitalized class) doesn't match our object patterns. On the roadmap.
- CrewAI `crew.kickoff()` is not detected — `kickoff` isn't in our method patterns.
- No inter-procedural analysis: if function A calls function B which calls `session.delete()`, only B is flagged.
- No import resolution: if you alias `import requests as r`, the scanner won't catch `r.post()`.

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

| Type | Repos | Avg unguarded |
|---|---|---|
| Application | 9 | 80% |
| Framework | 3 | 83% |
| Platform | 2 | 78% |
| SDK examples | 1 | 84% |
| Benchmark | 1 | 54% |

Applications — where teams wrote the tool calls themselves — show the same unguarded rate as frameworks. The gap between "the framework doesn't include guards" and "the team didn't add guards either" is consistent across both categories.

---

## What the scanner found, by category

| Category | Total unguarded | Present in X/16 repos | What it detects |
|----------|----------------|----------------------|-----------------|
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

**"76% unguarded" doesn't mean "76% of production agents are vulnerable."**

It means: 76% of tool calls in these open-source codebases have no detectable safeguards at the source code level. These are the repos that teams clone, extend, and deploy. Whether the teams who deploy them add their own guards is exactly the question diplomat-agent helps answer.

The scanner is static analysis. It sees what's in the code. It doesn't see:
- Runtime middleware or API gateways that may add auth/rate limiting
- Infrastructure-level protections (network policies, IAM roles)
- Deployment configurations that restrict access
- Guards added by teams in their private forks

That's why `# checked:ok — protected by [where]` exists. If a tool call is protected elsewhere, you annotate it and the scanner marks it as acknowledged.

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
| OpenAI Agents SDK `Runner.run_sync()` | Misses agent execution in this SDK | Roadmap |
| CrewAI `crew.kickoff()` | Misses crew launch pattern | Roadmap |
| Inter-procedural analysis | Can't follow function A → function B → side effect | Known limitation |
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
