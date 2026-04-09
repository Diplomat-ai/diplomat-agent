# OWASP Top 10 for Agentic Applications — diplomat-agent mapping

diplomat-agent maps its findings to the [OWASP Top 10 for Agentic Applications (2025)](https://owasp.org/www-project-top-10-for-large-language-model-applications/).

## Coverage matrix

| OWASP Code | Name | diplomat-agent coverage |
|------------|------|------------------------|
| ASI-01 | Agentic Identity & Access Abuse | `auth_check` detection (FastAPI `Depends`/`Security`) |
| ASI-02 | Tool & Function Call Exploitation | Core detection — all 11 effect categories |
| ASI-03 | Excessive Agency & Autonomy | `missing_hints` for missing confirmation, rate limit, bounds |
| ASI-04 | Agentic Orchestration Manipulation | `agent_invocation` detection |
| ASI-05 | Cross-Agent Data Contamination | Partial — LLM call detection (no taint tracking) |
| ASI-06 | Agentic Resource Overuse & Wallet Drain | `rate_limit` + `retry_bound` check detection |
| ASI-07 | Agentic Memory & Context Manipulation | Not covered — runtime concern |
| ASI-08 | Agentic Supply Chain Vulnerabilities | Not covered — MCP scanning on roadmap |
| ASI-09 | Agentic Logging & Monitoring Gaps | Not covered — runtime concern |
| ASI-10 | Multi-Agent Trust & Delegation Abuse | Partial — `agent_invocation` without auth check |

## What's covered: ASI-01 through ASI-06 and ASI-10

diplomat-agent covers 7 of 10 OWASP Agentic categories at the static analysis level:

- **ASI-01 / ASI-02 / ASI-03 / ASI-04 / ASI-06 / ASI-10** — detected through side-effect scanning and guard detection within Python function bodies.
- **ASI-05** — partially covered via LLM call detection. diplomat-agent identifies functions that call LLM APIs but does not perform taint tracking on the data flowing into those calls.

## What's NOT covered: ASI-07, ASI-08, ASI-09

These three categories are outside the scope of static code scanning:

- **ASI-07 (Memory & Context Manipulation)** — requires runtime monitoring of agent memory read/write operations. Static analysis can detect the *calls* (e.g. `delete_memory()`) but not the *intent* behind them.
- **ASI-08 (Supply Chain Vulnerabilities)** — requires analyzing MCP server registries and tool descriptions, not source code. MCP scanning is on the roadmap.
- **ASI-09 (Logging & Monitoring Gaps)** — runtime observability concern. Static analysis cannot verify that logs are collected, stored, and alerted on.

## How mapping works

Each detected side effect maps to one or more OWASP codes based on its category:

```
payment         → ASI-02, ASI-03
database_write  → ASI-02
database_delete → ASI-02, ASI-03
http_write      → ASI-02
llm_call        → ASI-02, ASI-05
agent_invocation→ ASI-02, ASI-04, ASI-10
email           → ASI-02
file_delete     → ASI-02, ASI-03
dynamic_code    → ASI-02, ASI-03
```

Missing governance checks add further codes:

```
no auth check   → ASI-01
no rate limit   → ASI-06
no retry bound  → ASI-06
no confirmation → ASI-03
```

## Output

OWASP codes appear in:
- **Terminal output** — `OWASP: ASI-01 · ASI-02 · ASI-06` line per tool
- **toolcalls.yaml** — `owasp: [ASI-01, ASI-02, ASI-06]` field per entry
- **SARIF** — `properties.owasp` array and rule tags
- **JSON** — included in tool object output

## References

- [OWASP Top 10 for Agentic Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [OWASP Agentic Security Initiative](https://genai.owasp.org)
