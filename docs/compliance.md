# Compliance and regulatory alignment

> **diplomat-agent is a technical scanner, not a compliance tool.** It provides evidence that supports compliance workflows but does not constitute legal compliance with any regulation. Consult legal counsel for your specific regulatory obligations.

## EU AI Act (enforcement begins August 2026)

Article 9 of the EU AI Act requires risk management systems for high-risk AI, including documentation of system capabilities and limitations.

diplomat-agent provides:
- **Pre-deployment inventory** of agent capabilities — every function that can change state in the real world, documented in `toolcalls.yaml`
- **Governance gap analysis** — which tool calls have no checks (validation, rate limits, auth, confirmation)
- **Auditable evidence** — `toolcalls.yaml` is a committable, diffable artifact that records the governance state at each release

This does not replace a risk management system. It provides one input to that system: a behavioral inventory at the source code level.

## OWASP Top 10 for Agentic Applications

diplomat-agent covers 7 of 10 OWASP Agentic categories at the static analysis level (ASI-01 through ASI-06 and ASI-10).

See [OWASP Agentic Top 10 mapping](owasp-agentic-mapping.md) for the full coverage matrix.

## NIST AI Agent Standards Initiative (February 2026)

The NIST Interoperability Profile (expected Q4 2026) is anticipated to require agents to declare their capabilities. diplomat-agent's per-tool-call inventory aligns with this anticipated need — each function's side effects and governance state are recorded in a machine-readable format.

## DORA (Digital Operational Resilience Act — financial services)

DORA requires financial entities to understand the operational capabilities of their ICT systems. `toolcalls.yaml` provides a versionable record of what an AI agent can do to external systems — database writes, API calls, payments, emails — and whether governance checks exist for each capability.

## What diplomat-agent provides for compliance workflows

| Compliance need | diplomat-agent output |
|----------------|----------------------|
| Capability inventory | `toolcalls.yaml` — complete registry of tool calls with side effects |
| Risk surface documentation | Per-function missing checks and OWASP codes |
| Audit trail | Committed `toolcalls.yaml` in git history, diffable across releases |
| CI gate | `--fail-on-unchecked` prevents new unreviewed tool calls from merging |
| Standards alignment | OWASP Agentic mapping, SARIF for GitHub Code Scanning |
