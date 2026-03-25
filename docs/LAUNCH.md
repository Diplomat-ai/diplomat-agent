# diplomat-agent — Launch Posts

Ready to copy-paste. All claims backed by data from the issue corpus (2,332 issues) and real scans (Skyvern, SurfSense, FinRobot).

---

## Post 1: Hacker News (Show HN)

**Timing:** Publish the repo Sunday evening. Post on HN Tuesday 9-10am ET (13-14h UTC). Post on Reddit Sunday evening or Monday morning. Avoid Mondays for HN (crowded) and Fridays (low engagement). Observed pattern: openai-agents-python and LangGraph announcements peak engagement mid-week.

---

**Title:** Show HN: diplomat-agent -- find every unguarded tool call in your Python AI agent

**Body:**

I built diplomat-agent because I kept seeing the same failure in agentic codebases: a tool call that writes to the DB, sends an email, or charges a card -- with nothing preventing it from firing twice, without auth, or with unbounded inputs.

We analyzed 2,332 GitHub issues across LangGraph, CrewAI, AutoGen, OpenAI Agents SDK, and others. 1,075 document tool calls executing multiple times without idempotency. 325 document human-in-the-loop interrupts that fail silently.

diplomat-agent scans your Python source with AST analysis. No runtime, no config, no network calls. It finds every function that triggers a real-world action and checks whether protections exist.

```
$ diplomat-agent ./skyvern/
382 tool calls · 307 with no checks · 66 partial · 9 confirmed
```

It generates a `toolcalls.yaml` you commit to your repo -- a diffable inventory of your agent's impact surface. Add `--fail-on-unchecked` in CI to block PRs that add unguarded tool calls.

Ran it on Skyvern (20.9k stars): 80% of tool calls have no checks. SurfSense (13.3k stars): 53% unguarded.

Zero dependencies. Apache-2.0. Runs in <2 seconds on a 600-file codebase.

https://github.com/Diplomat-ai/diplomat-agent

---

## Post 2: Reddit (r/LocalLLaMA or r/machinelearning)

---

**Title:** 80% of tool calls in a 20k-star AI agent have zero protection. Here's a scanner that finds them.

**Body:**

We analyzed 2,332 GitHub issues across the major agent frameworks. The #1 operational failure (1,075 issues): a tool call that fires multiple times when it should fire once. No idempotency key. No rate limit. No circuit breaker.

So I built diplomat-agent. It's a Python AST scanner that finds every function in your codebase that can change the real world (DB writes, payments, emails, API calls, LLM invocations) and checks whether protections exist before execution.

Ran it on real open-source agents:

- Skyvern (20.9k stars): 382 tool calls, 307 unguarded (80%)
- SurfSense (13.3k stars): 319 tool calls, 169 unguarded (53%)
- FinRobot (6.5k stars): 27 tool calls, 18 unguarded (67%)

The output is a `toolcalls.yaml` you commit to your repo. Think of it as an SBOM for your agent's tool calls. You can see exactly what your agent can do to the real world, what's protected, and what isn't.

```
pip install diplomat-agent
diplomat-agent ./my_agent/
```

Zero dependencies. No runtime integration. No network calls. <2 seconds on a 600-file project.

CI integration: `--fail-on-unchecked` returns exit code 1 if any new tool call has no checks.

Apache-2.0: https://github.com/Diplomat-ai/diplomat-agent

What checks do you run before your agents touch production?

---

## Post 3: Twitter/X Thread

---

**Tweet 1 (hook — terminal output):**

```
$ diplomat-agent ./skyvern/
382 tool calls · 307 with no checks · 66 partial · 9 confirmed

⚠ terminate                 .../script_skyvern_page.py:868
  actions:
    shutil.rmtree(temp_dir)
    os.kill(pid, signal.SIGTERM)
  checks: none
```

Skyvern has 20.9k GitHub stars. 80% of its tool calls have zero protection.

---

**Tweet 2 (the pain, with data):**

We analyzed 2,332 GitHub issues across LangGraph, CrewAI, AutoGen, and OpenAI Agents SDK.

The #1 failure pattern: a tool call that executes multiple times when it should execute once.

1,075 issues. No idempotency. No rate limit. Just a for loop and a prayer.

---

**Tweet 3 (what it does):**

diplomat-agent scans your Python agent's source code with AST analysis.

It finds every function that can change the real world -- DB writes, payments, emails, LLM calls -- and checks if protections exist.

Zero dependencies. No runtime. <2 seconds.

---

**Tweet 4 (the registry):**

The output is a `toolcalls.yaml` you commit to your repo.

Think SBOM, but for agent tool calls. Every tool call, its checks, what's missing. Diffable on PRs. Sign off with `# checked:ok`.

No other tool produces this.

---

**Tweet 5 (CTA):**

```
pip install diplomat-agent
diplomat-agent ./my_agent/
```

Apache-2.0. Try it on your agent, share what you find.

https://github.com/Diplomat-ai/diplomat-agent
