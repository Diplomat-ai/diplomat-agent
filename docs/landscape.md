# How diplomat-agent compares to other tools

diplomat-agent is a static analysis scanner that inventories tool calls with real-world side effects in Python AI agent codebases and checks whether governance mechanisms (validation, rate limits, auth, confirmation) exist around them.

This page describes how it differs from other tools in the agentic security space. Every claim is verifiable by reading the linked repositories.

## Comparison matrix

| Tool | Approach | Agent-specific | Side-effect inventory | Guard detection | OWASP Agentic | Output format |
|------|----------|---------------|----------------------|-----------------|---------------|---------------|
| **diplomat-agent** | AST static analysis | Yes | Yes — 11 categories | Yes — 7 check types | ASI-01–06, 10 | Terminal, JSON, YAML, SARIF, CSAF |
| Agentic Radar | LLM-assisted graph | Yes | Partial — workflow level | No | No | Graph visualization |
| agent-audit | LLM-assisted audit | Yes | Partial — prompt-based | No | Yes | Markdown |
| Snyk Agent Scan | MCP registry scan | Yes | No — description-based | No | No | JSON |
| Semgrep | Pattern matching | 3 agentic rules | No | No | No | SARIF, JSON |
| Cisco Skill Scanner | MCP description scan | Yes | No — description-based | No | No | JSON |
| eslint-plugin-vercel-ai-security | ESLint rules | Yes (JS/TS) | Partial | No | Yes | ESLint |
| CodeQL | Dataflow analysis | No | No | No | No | SARIF |
| Bandit | AST pattern matching | No | No | No | No | JSON, SARIF |
| SonarQube | Multi-language SAST | No | No | No | No | Dashboard |

## How diplomat-agent differs

### vs. Agentic Radar

Agentic Radar builds a workflow graph showing how agents connect and delegate. diplomat-agent works at the function body level — it reads every function, identifies what it can do to the real world, and checks whether guards exist in the same scope. These are complementary: Agentic Radar maps the *topology*, diplomat-agent maps the *behavior* at each node.

### vs. Snyk Agent Scan

Snyk scans MCP server *descriptions* (tool manifests) for risk signals. diplomat-agent scans the actual *implementation code* — the Python functions that execute when a tool is called. A tool description might say "reads user data" while the implementation calls `session.delete()`. diplomat-agent catches the implementation, not the description.

### vs. agent-audit

agent-audit uses an LLM to analyze code and produce a vulnerability report. diplomat-agent uses deterministic AST parsing — no LLM in the loop, no API key required, reproducible results. agent-audit finds potential vulnerabilities; diplomat-agent inventories governance gaps. Different questions, different approaches.

### vs. Semgrep

Semgrep has ~3 rules targeting agentic patterns (out of 5,800+ total rules). diplomat-agent has 40+ patterns specifically designed for AI agent side effects and 7 guard detection types. Semgrep excels at general SAST; diplomat-agent is purpose-built for the "does this tool call have guardrails" question.

### vs. Traditional SAST (CodeQL, Bandit, SonarQube)

Traditional SAST tools don't have agent-specific rules. They can find SQL injection or command injection, but they don't answer "does this function that calls `stripe.Refund.create()` have a bounds check on the amount?". diplomat-agent fills that specific gap.

### vs. AI-BOM standards (CycloneDX, SPDX AI Profile)

AI-BOM formats inventory what an agent is *made of* — models, libraries, datasets, training data. diplomat-agent's `toolcalls.yaml` inventories what an agent can *do* — which functions have side effects and whether guards exist. These are complementary layers: CycloneDX tells you what's in the box, `toolcalls.yaml` tells you what the box can do.

## The governance gap

Taint analysis (CodeQL, Semgrep) answers: "can untrusted data reach a dangerous sink?" This is important but doesn't answer the governance question: "does this function have the guardrails you'd expect for its impact?"

A `stripe.Refund.create(amount=amount)` with proper input sanitization still needs a bounds check on the amount and a rate limit. A `session.delete(record)` with no SQL injection risk still needs a confirmation step when called by an autonomous agent. These are governance checks, not security vulnerabilities in the traditional sense.

diplomat-agent scans for both the effects and the checks. The gap between them is the governance surface.

## What diplomat-agent doesn't do

- **Runtime enforcement** — diplomat-agent is a scanner, not a policy engine. See [Diplomat](https://diplomat.run) for runtime governance.
- **Taint tracking** — no dataflow analysis. If you need to trace untrusted input to a sink, use Semgrep or CodeQL.
- **MCP server scanning** — currently scans Python source, not MCP manifests. On the roadmap.
- **TypeScript** — Python only. TypeScript on the roadmap.
- **Import resolution** — if you alias `import requests as r`, the scanner won't catch `r.post()`.
