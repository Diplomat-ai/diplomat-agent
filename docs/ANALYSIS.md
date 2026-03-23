# agent-canary — Launch Analysis

Data sources: 2,332 classified issues across 6 repos (LangGraph, CrewAI, AutoGen, OpenAI Agents SDK, Claude Code, Vercel AI SDK). 3 real-world scans (Skyvern: 382 tool calls, SurfSense: 319 tool calls, FinRobot: 27 tool calls). 5 competitor/ecosystem repo benchmarks.

## ICP (Ideal Contributor Profile)

### 1. Backend engineer shipping an agent to production (Python, 3-7 years)

- **Stack:** FastAPI + SQLAlchemy + LangGraph/CrewAI + Stripe/Twilio
- **Constraint:** First agent going to prod; no prior security audit process for agentic code
- **Optimizes for:** Not getting paged at 3am because an LLM retried a payment 4 times
- **Evidence:** 1,075 issues tagged `tool_called_multiple` — the #1 operational failure pattern. Skyvern scan: 307/382 tool calls unguarded (80%). Titles like "Background runs re-executed after ~180s" (LangGraph #7213), "custom BaseTool wrapper enters infinite tool-use loop" (CrewAI #4495).

### 2. Security-conscious tech lead doing pre-launch review (Python, 5-10 years)

- **Stack:** Any Python agent framework + CI/CD
- **Constraint:** Needs auditable evidence of tool call coverage before launch sign-off
- **Optimizes for:** A versionable artifact that proves every tool call was reviewed
- **Evidence:** CrewAI #4651 "Security best practices guide for CrewAI agents" (signal_score=3). CrewAI #4593 "Enforce fail-closed defaults for unsafe tool execution." Claude Code #29225 "Add guardrails to prevent accidental exposure of private code." No competitor produces a versionable registry — agentic-radar outputs HTML, Invariant requires runtime integration.

### 3. Open-source agent maintainer managing contributor risk (Python, 3+ years)

- **Stack:** Multi-contributor repo with tool-calling code spread across modules
- **Constraint:** PRs add new tool calls without the maintainer knowing what they touch
- **Optimizes for:** CI gate that catches new unguarded tool calls before merge
- **Evidence:** 797/1,429 `breaking_change` issues still open (56%). OpenAI Agents #2756 "Agent Identity Verification for Cross-Organization Handoffs." SurfSense scan: 169 unguarded tool calls including `_cleanup_stale_notifications` writing to DB with no auth check. `--fail-on-unchecked` catches these at PR time.

---

## Top 10 Pains (ranked by frequency x impact)

| # | Pain | Frequency (issues) | Bloquant? | Example verbatim | Covered by agent-canary? |
|---|------|-------------------|------------|------------------|--------------------------|
| 1 | Tool executes multiple times when it should execute once | 1,075 (25.0%) | Yes — duplicate payments, duplicate DB writes | "custom BaseTool wrapper gets called without args and enters infinite tool-use loop" (CrewAI #4495) | **Yes** — flags missing idempotency keys, rate limits |
| 2 | No check before destructive tool call | 70 direct + implicit in 511 race_condition | Yes — unprotected writes, deletes | "SyncPregelLoop.put_writes caches ERROR/INTERRUPT writes (async has guard, sync does not)" (LangGraph) | **Yes** — core detection: finds tool calls with zero checks |
| 3 | Race condition between concurrent tool calls | 511 (11.9%) | Yes — corrupted state, lost writes | "Run Cancellation Causes Loss of Streamed State Not Yet Persisted as a Checkpoint" (LangGraph) | **Partial** — flags missing guards but no concurrency analysis |
| 4 | Human-in-the-loop interrupt fails, tool executes anyway | 325 (7.6%) | Yes — the human said stop but the tool ran | "Resuming after interrupt doesn't reuse prior task outputs when interrupt is in subgraph" (LangGraph #6792) | **No** — no interrupt flow analysis |
| 5 | LLM cost explosion from unbounded retries | 128 (3.0%) | Yes — $500 OpenAI bill from a loop | "Background runs re-executed after ~180s despite shutdown grace period" (LangGraph #7213) | **Yes** — flags missing max_retries, stop_after_attempt |
| 6 | Tool result orphaned — call happened, result lost | 130 (3.0%) | Yes — side effect executed but system doesn't know | "Multiple Tool Results for Single Tool Call with LangGraph Human Approval Flow" (LangGraph) | **No** — requires runtime tracing |
| 7 | No visibility into what tools can do | implicit across all | No — but blocks audits | "needsApproval tools not returning a tool_result block" (Vercel AI #10980) | **Yes** — the entire point of toolcalls.yaml |
| 8 | MCP tool calls with no auth verification | 70+ across repos | Yes — any MCP client can invoke | "MCP tool calling has no per-message authentication or integrity verification" (CrewAI #4875) | **Yes** — flags tool calls without auth checks |
| 9 | Supply chain: dependency introduces unguarded tool | 591 (13.8%) | No — but hard to catch in review | "Where to find 'invariant.detectors'?" (Invariant) — even security tools have discoverability issues | **Partial** — scans vendored code but not installed packages |
| 10 | No CI gate for new tool calls | 0 dedicated issues but 797 open breaking_changes | No — but causes regressions | "Enforce fail-closed defaults for unsafe tool execution" (CrewAI #4593) | **Yes** — `--fail-on-unchecked` exit code 1 |

---

## Anti-patterns that kill adoption

### 1. No real output in the first 10 lines of README

**Proof:** LangGraph README: no terminal output in first 100 lines. CrewAI README: marketing-focused content about AMP Suite, no runnable example. Only openai-agents-python shows a real code snippet with output.
**Impact:** Users bounce. Time-to-first-result for LangGraph is ~10 min (requires LangSmith setup). agent-canary must show terminal output before the fold.

### 2. HTML-only reports (no CLI-native output)

**Proof:** agentic-radar generates an HTML report — requires opening a browser. No terminal output, no CI-friendly format. Invariant requires writing Python policy code before seeing results.
**Impact:** Doesn't fit in `git diff` review. Not CI-native. agent-canary's terminal + YAML output is the differentiator — preserve it.

### 3. Requiring runtime integration for static analysis

**Proof:** Invariant: "Deployed between your application and your MCP servers or LLM provider." Requires code changes and runtime hooks. agentic-radar: static but outputs HTML only.
**Impact:** Adoption friction. agent-canary runs on source code with zero config. Keep it that way.

### 4. No versionable artifact

**Proof:** Neither agentic-radar nor Invariant produce a file you commit to git. agentic-radar outputs HTML. Invariant produces runtime logs. Neither creates a reviewable, diffable registry.
**Impact:** Security reviews can't track progress over time. toolcalls.yaml is agent-canary's moat.

### 5. Jargon-first positioning ("guardrails", "security posture", "threat model")

**Proof:** Invariant: "contextual guardrails for securing agent systems." agentic-radar: "security scanner for your agentic workflows." The community says "tool calls" (1,075 issues with `tool_called_multiple`) not "guardrails." CrewAI issue titles use "tool call", "tool execution", never "guardrail."
**Impact:** Devs don't identify. agent-canary should say "tool calls" and "checks" — matches 701 mentions in the issue corpus vs 8 for "scan."

---

## Opportunites strategiques

### 1. Own the "inventory" category (→ Pain #7, #10)

No competitor produces a versionable, diffable artifact. agentic-radar outputs HTML. Invariant requires runtime. toolcalls.yaml is a new category: the SBOM for agent tool calls. Evidence: agentic-radar issue "Collaboration opportunity: ai-bom for SBOM generation" — the community is asking for exactly this.

### 2. CI-native by default (→ Pain #10, #2)

`--fail-on-unchecked` with exit code 1 is the fastest path to adoption. 797 open `breaking_change` issues show that regressions happen on every PR. No competitor has a one-line CI integration. The GitHub Actions YAML should be in the README above the fold.

### 3. Idempotency detection as killer feature (→ Pain #1)

1,075 issues about tool calls executing multiple times. This is the #1 operational pain. agent-canary already detects missing `get_or_create`, `upsert`, `ON CONFLICT`. No competitor flags this. Lead marketing with this: "Your agent called stripe.Refund.create 4 times. agent-canary would have caught it."

### 4. Real-project benchmarks as proof (→ Pain #7)

Skyvern: 307/382 unguarded (80%). SurfSense: 169/319 unguarded (53%). These are real projects with real stars. Show the numbers. No competitor publishes benchmarks on named open-source projects.

### 5. Bridge to runtime with Diplomat (→ Pain #3, #4)

agent-canary is static analysis. Race conditions (#3) and interrupt failures (#4) need runtime. Position agent-canary as the map, Diplomat as the territory control. The toolcalls.yaml becomes the config source for runtime enforcement. This is the business model — give away the scanner, sell the runtime.
